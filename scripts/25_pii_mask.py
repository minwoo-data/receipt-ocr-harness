"""25_pii_mask.py - the masking experiment's commands (plan: docs/plan-pii-mask.md, "Order and budget").

Wiring only: every decision lives in src/harness/mask.py and src/harness/pii_run.py, which are frozen before
any label is requested. Every subcommand takes --results, --manifest and --run (default r0) and runs from
the repository root. Steps add their subcommands as they are built:

    freeze   (step 2)  record the code provenance of mask.py and pii_run.py in results*/pii/<run>/freeze.json

    python scripts/25_pii_mask.py freeze --results results --manifest data/manifest/sroie300.jsonl
    python scripts/25_pii_mask.py freeze --results results_wild --manifest data/manifest/wild200.jsonl

A frozen run is never re-frozen with different code: a change after the freeze is a revision (--run rev1).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from harness import mask  # noqa: E402


def cmd_freeze(P: dict, args) -> None:
    prov = mask.code_provenance([P["sidecar"]])
    if prov["new_modules"]:
        raise SystemExit(f"unexpected modules {prov['new_modules']}")
    doc = {"format_version": 1, "run": P["run"], "dataset": P["dataset"], "frozen": date.today().isoformat(),
           "plan": "docs/plan-pii-mask.md", "provenance": prov}
    f = P["freeze"]
    if f.exists():
        old = json.loads(f.read_text(encoding="utf-8"))
        if old["provenance"] == prov:
            print(f"{f.relative_to(ROOT).as_posix()}: already frozen with the same code ({old['frozen']})")
            return
        changed = sorted(k for k, v in prov["modules"].items() if old["provenance"]["modules"].get(k) != v)
        raise SystemExit(f"{f.relative_to(ROOT).as_posix()} is frozen with other code (changed: {changed}); "
                         f"a change after the freeze is a revision: use --run rev<k>")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"froze {P['dataset']} {P['run']}: {len(prov['modules'])} modules, sidecar "
          f"{next(iter(prov['sidecars']))}, -> {f.relative_to(ROOT).as_posix()}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("freeze",):
        s = sub.add_parser(name)
        s.add_argument("--results", required=True)
        s.add_argument("--manifest", required=True)
        s.add_argument("--run", default="r0")
    args = ap.parse_args()
    P = mask.pii_paths(ROOT / args.results, ROOT / args.manifest, run=args.run)
    {"freeze": cmd_freeze}[args.cmd](P, args)


if __name__ == "__main__":
    main()
