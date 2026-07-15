#!/usr/bin/env python3
"""Deterministic groundedness audit for the completion files.

For each completions/<tool>.fish, extract every token the completion offers
(long options via -o/-l, short flags via -s, and -a argument values /
subcommand names) and check whether each appears verbatim in the tool's
reference text (man page + --help/-h/help output). Tokens that appear nowhere
in the reference are reported as candidate fabrications for human triage.

This is a ground-truth string match, not an LLM judgment: no hallucination,
but false positives are expected (real tokens documented elsewhere, or values
that are user-supplied rather than enumerated). Triage the output.

Usage: python3 tests/audit_grounding.py [tool ...]
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMP = os.path.join(ROOT, "completions")

# Tools whose help probes have side effects, mapped to the probe list that is
# safe for them. screencapture treats ANY non-option argument as an output
# filename and takes a real screenshot (shutter sound and all) — so it gets
# no help probes, man page only.
SAFE_HELP_ARGS = {
    "screencapture": [],
}
DEFAULT_HELP_ARGS = [["--help"], ["-h"], ["help"]]

# Extra reference commands for tools whose vocabulary lives in sub-help or
# capability output that man + top-level help do not carry. Same constraints
# as the help probes: fast, unprivileged, no side effects.
EXTRA_REF_CMDS = {
    "scutil": [["scutil", "--nc", "help"]],
    "pmset": [["pmset", "-g", "cap"]],
}


def reference_text(tool: str) -> str:
    """man page + help output, best-effort, never hangs."""
    chunks = []
    try:
        man = subprocess.run(["man", tool], capture_output=True, text=True, timeout=10)
        chunks.append(subprocess.run(["col", "-b"], input=man.stdout,
                                     capture_output=True, text=True, timeout=10).stdout)
    except Exception:
        pass
    probes = [[tool] + args for args in SAFE_HELP_ARGS.get(tool, DEFAULT_HELP_ARGS)]
    probes += EXTRA_REF_CMDS.get(tool, [])
    for argv in probes:
        try:
            r = subprocess.run(argv, capture_output=True, text=True,
                               timeout=5, stdin=subprocess.DEVNULL)
            chunks.append(r.stdout)
            chunks.append(r.stderr)
        except Exception:
            pass
    return "\n".join(chunks)


def offered_tokens(path: str):
    """Return (flags, values) token sets the completion offers."""
    flags = set()   # option names, kept WITH a leading dash for matching
    values = set()  # -a argument values and subcommand names
    raw = open(path, encoding="utf-8").read()
    raw = re.sub(r"\\\n\s*", " ", raw)   # join backslash-continued complete statements
    for line in raw.splitlines():
        s = line.strip()
        if not s.startswith("complete"):
            continue
        # long options: -o name / -l name
        for m in re.finditer(r"\s-[ol]\s+([A-Za-z0-9][A-Za-z0-9_-]*)", s):
            flags.add("-" + m.group(1))            # match against -name and --name later
        # short flags: -s X
        for m in re.finditer(r"\s-s\s+([A-Za-z0-9])\b", s):
            flags.add("-" + m.group(1))
        # -a values: quoted list  -a 'a b c'   or bareword  -a word
        for m in re.finditer(r"\s-a\s+'([^']*)'", s):
            blob = m.group(1)
            if blob.strip().startswith("("):       # command substitution, not literal
                continue
            # entries of the form  value\t"description" — take only the value
            for vm in re.finditer(r'([^\s\'"]+?)\\t"[^"]*"', blob):
                values.add(vm.group(1))
            # strip those entries, then take any remaining bare-word values
            rest = re.sub(r'[^\s\'"]+?\\t"[^"]*"', " ", blob)
            for tok in rest.split():
                if tok and not tok.startswith("(") and '"' not in tok and "\\t" not in tok:
                    values.add(tok)
        for m in re.finditer(r"\s-a\s+([A-Za-z0-9][A-Za-z0-9_.:-]*)(?:\s|$)", s):
            values.add(m.group(1))
    return flags, values


def grounded(token: str, ref: str, ref_lower: str) -> bool:
    """Is the token present in the reference text?"""
    t = token.lstrip("-")
    if len(t) <= 1:
        # short flag: look for -t form (case-sensitive — flags are case-significant)
        return ("-" + t) in ref
    if token in ref:                      # exact, with dash if it had one
        return True
    if t in ref:                          # bare name (man may not prefix the dash)
        return True
    if ("--" + t) in ref:                 # man documents a double-dash form
        return True
    # last resort, case-insensitive for value enums (format names etc.)
    return t.lower() in ref_lower


def main():
    only = set(sys.argv[1:])
    files = sorted(os.listdir(COMP))
    total_ungrounded = 0
    report = []
    for fn in files:
        if not fn.endswith(".fish"):
            continue
        tool = fn[:-5]
        if only and tool not in only:
            continue
        ref = reference_text(tool)
        ref_lower = ref.lower()
        flags, values = offered_tokens(os.path.join(COMP, fn))
        if not ref.strip():
            report.append((tool, None, [], []))   # no reference available
            continue
        bad_flags = sorted(f for f in flags if not grounded(f, ref, ref_lower))
        bad_vals = sorted(v for v in values if not grounded(v, ref, ref_lower))
        total_ungrounded += len(bad_flags) + len(bad_vals)
        report.append((tool, len(flags) + len(values), bad_flags, bad_vals))

    print(f"{'TOOL':<16} {'tokens':>6} {'ungrounded':>10}")
    print("-" * 40)
    for tool, n, bf, bv in report:
        if n is None:
            print(f"{tool:<16} {'?':>6}   NO REFERENCE TEXT")
            continue
        print(f"{tool:<16} {n:>6} {len(bf)+len(bv):>10}")
        for f in bf:
            print(f"    FLAG  {f}")
        for v in bv:
            print(f"    VALUE {v}")
    print("-" * 40)
    print(f"total candidate-ungrounded tokens: {total_ungrounded}")


if __name__ == "__main__":
    main()
