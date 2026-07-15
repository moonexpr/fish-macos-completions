#!/usr/bin/env python3
"""Cross-model consensus over adk_verify.py --json reports.

Reads one or more JSON report files (as produced by
`tests/adk_verify.py --json --model ...`), one per model, and prints a
per-token verdict matrix plus a consensus column:

  consensus = the strictest verdict any model gave, ranked
              FABRICATED > PLAUSIBLE > VALID
  (a token is only as trustworthy as its most skeptical judge)

Usage:
    python3 tests/consensus_report.py report1.json report2.json ...

Model names are derived from the file names (verify-<name>.json -> <name>).
"""
import json
import os
import sys

RANK = {"FABRICATED": 2, "PLAUSIBLE": 1, "VALID": 0}


def model_name(path):
    base = os.path.basename(path)
    if base.startswith("verify-") and base.endswith(".json"):
        return base[len("verify-"):-len(".json")]
    return base


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    reports = {}   # model -> {(tool, token): verdict}
    errors = []    # (model, tool, message)
    for path in sys.argv[1:]:
        model = model_name(path)
        data = json.load(open(path, encoding="utf-8"))
        verdicts = {}
        for tool, body in data.items():
            if "error" in body:
                errors.append((model, tool, body["error"][:80]))
                continue
            for v in body.get("verdicts", []):
                verdict = str(v.get("verdict", "?")).upper()
                verdicts[(tool, v.get("token", "?"))] = verdict
        reports[model] = verdicts

    models = sorted(reports)
    tokens = sorted({k for r in reports.values() for k in r})
    width = max((len(m) for m in models), default=8)

    header = f"{'TOOL':<14} {'TOKEN':<28} " + " ".join(f"{m:<{width}}" for m in models) + " CONSENSUS"
    print(header)
    print("-" * len(header))
    counts = {}
    for tool, token in tokens:
        row = [reports[m].get((tool, token), "-") for m in models]
        seen = [v for v in row if v in RANK]
        consensus = max(seen, key=RANK.get) if seen else "?"
        counts[consensus] = counts.get(consensus, 0) + 1
        print(f"{tool:<14} {token:<28} " + " ".join(f"{v:<{width}}" for v in row) + f" {consensus}")

    print("-" * len(header))
    print("consensus totals: " + " / ".join(f"{k}: {n}" for k, n in sorted(counts.items())))
    if errors:
        print("\nmodel errors (tool not judged by that model):")
        for model, tool, msg in errors:
            print(f"  {model:<{width}} {tool:<14} {msg}")
    return 1 if counts.get("FABRICATED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
