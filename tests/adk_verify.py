#!/usr/bin/env python3
"""LLM triage of the deterministic groundedness audit, via Google ADK + Ollama.

audit_grounding.py is a verbatim string match against the tool's man/help
text: zero hallucination, but false positives (tokens documented with
different casing, in prose, in Apple's online docs, or inherently
user-supplied values). This script feeds each candidate-ungrounded token to
an ADK agent backed by an Ollama-hosted model, which judges the token against
the same reference text and classifies it:

  VALID       - real option/value for this tool (reference supports it,
                possibly indirectly)
  PLAUSIBLE   - cannot be confirmed from the reference, but consistent with
                the tool's documented interface; needs human check
  FABRICATED  - contradicts the reference or looks invented

The deterministic audit remains the ground truth; this pass only *ranks* its
findings for triage before upstreaming to fish-shell. Verdicts are advisory.

Setup (per https://adk.dev/agents/models/ollama/):
    python3 -m venv .venv && .venv/bin/pip install google-adk litellm
    export OLLAMA_API_BASE=http://localhost:11434   # set automatically below

Usage:
    .venv/bin/python tests/adk_verify.py [tool ...]
    .venv/bin/python tests/adk_verify.py --model ollama_chat/glm-5.2:cloud

Note: a `:cloud` Ollama model proxies inference to ollama.com — the man-page
excerpts and token names are sent off-machine.
"""
import argparse
import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_grounding import COMP, grounded, offered_tokens, reference_text

os.environ.setdefault("OLLAMA_API_BASE", "http://localhost:11434")

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types

DEFAULT_MODEL = "ollama_chat/glm-5.2:cloud"
MAX_REF_CHARS = 60_000  # man pages are small; cap defensively

INSTRUCTION = """\
You audit fish-shell tab completions for macOS command-line tools before they
are submitted to the official fish-shell repository.

You are given the reference documentation for ONE tool (its man page and
--help output) and a list of tokens a completion file offers that a verbatim
string match could NOT find in that reference.

For EACH token, decide:
  VALID      - the reference actually supports it (different casing, hyphen
               variant, documented in prose, an obvious enumeration member).
  PLAUSIBLE  - not confirmable from the reference but consistent with the
               tool's interface (e.g. an undocumented-but-real Apple flag,
               a value the tool accepts though the man page omits it).
  FABRICATED - contradicts the reference or appears invented.

Judge strictly from the reference text plus general knowledge of macOS
tooling. Do not assume a token is valid merely because it looks plausible in
shape; FABRICATED is the correct verdict when nothing supports it.

Respond with ONLY a JSON array, no prose, one object per token:
  [{"token": "...", "kind": "flag"|"value", "verdict": "VALID"|"PLAUSIBLE"|"FABRICATED", "reason": "<one line>"}]
"""


def collect_findings(only):
    """Run the deterministic audit; return {tool: {"flags": [...], "values": [...]}}."""
    findings = {}
    for fn in sorted(os.listdir(COMP)):
        if not fn.endswith(".fish"):
            continue
        tool = fn[:-5]
        if only and tool not in only:
            continue
        ref = reference_text(tool)
        if not ref.strip():
            findings[tool] = None  # no reference to judge against
            continue
        ref_lower = ref.lower()
        flags, values = offered_tokens(os.path.join(COMP, fn))
        bad_flags = sorted(f for f in flags if not grounded(f, ref, ref_lower))
        bad_vals = sorted(v for v in values if not grounded(v, ref, ref_lower))
        if bad_flags or bad_vals:
            findings[tool] = {"flags": bad_flags, "values": bad_vals, "ref": ref}
    return findings


def parse_verdicts(text):
    """Extract the JSON array from the model's reply, tolerating fences."""
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


async def judge_tool(runner, user_id, tool, entry):
    tokens = [{"token": t, "kind": "flag"} for t in entry["flags"]] + [
        {"token": t, "kind": "value"} for t in entry["values"]
    ]
    prompt = (
        f"Tool: {tool}\n\n"
        f"Tokens to judge (JSON):\n{json.dumps(tokens, indent=1)}\n\n"
        f"Reference documentation for {tool} (man page + help output):\n"
        f"-----\n{entry['ref'][:MAX_REF_CHARS]}\n-----\n"
        f"Return the JSON array of verdicts now."
    )
    session = await runner.session_service.create_session(
        app_name=runner.app_name, user_id=user_id
    )
    reply = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        if event.content and event.content.parts:
            reply.extend(p.text for p in event.content.parts if p.text)
    verdicts = parse_verdicts("".join(reply))
    if verdicts is None:
        return tool, None, "".join(reply)[-400:]
    return tool, verdicts, None


async def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tools", nargs="*", help="limit to these tools")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"LiteLLM model id (default: {DEFAULT_MODEL}); "
                         "use the ollama_chat/ provider, not ollama/")
    ap.add_argument("--json", action="store_true", help="emit raw JSON report")
    args = ap.parse_args()

    findings = collect_findings(set(args.tools))
    judged = {t: e for t, e in findings.items() if e}
    skipped = sorted(t for t, e in findings.items() if e is None)
    if not judged:
        print("deterministic audit found no candidate-ungrounded tokens to judge")
        return 0

    agent = Agent(
        model=LiteLlm(model=args.model),
        name="completion_auditor",
        description="Judges fish completion tokens against tool documentation.",
        instruction=INSTRUCTION,
    )
    runner = InMemoryRunner(agent=agent, app_name="fish-completion-audit")

    report = {}
    for tool in sorted(judged):
        tool, verdicts, err = await judge_tool(runner, "auditor", tool, judged[tool])
        if verdicts is None:
            report[tool] = {"error": f"unparseable reply: {err}"}
        else:
            report[tool] = {"verdicts": verdicts}

    if args.json:
        print(json.dumps(report, indent=1))
        return 0

    counts = {"VALID": 0, "PLAUSIBLE": 0, "FABRICATED": 0}
    for tool in sorted(report):
        body = report[tool]
        print(f"\n== {tool} ==")
        if "error" in body:
            print(f"  MODEL ERROR: {body['error']}")
            continue
        for v in body["verdicts"]:
            verdict = str(v.get("verdict", "?")).upper()
            counts[verdict] = counts.get(verdict, 0) + 1
            print(f"  {verdict:<10} {v.get('kind', '?'):<5} {v.get('token', '?'):<28} {v.get('reason', '')}")
    if skipped:
        print(f"\nno reference text (not judged): {', '.join(skipped)}")
    print("\n" + " / ".join(f"{k}: {n}" for k, n in counts.items() if n))
    return 1 if counts.get("FABRICATED") else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
