"""17_gate_experiment.py - Baseline gates vs baseline + one optional gate, on one results root.

The optional gate (verify.check_total_label, --gates total_label) was designed on
SROIE 300 only and frozen before WildReceipt 200 was scored. This script records
the SHA-256 of src/harness/verify.py next to the numbers, so the code that
produced the held-out result can be matched to the frozen commit.

    python scripts/04_harness.py --results results --gates total_label --out results/gate_total_label/harness
    python scripts/17_gate_experiment.py --results results --role "dev (gate designed here)"
    (same two commands with results_wild and --manifest data/manifest/wild200.jsonl, --role "held-out")
Outputs: <results>/gate_total_label/comparison.json, comparison.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ("harness", "local_only", "harness_ladder")


def load(d: Path):
    P = {p["policy"]: p for p in json.loads((d / "policies.json").read_text(encoding="utf-8"))}
    W = {w["tier"]: w for w in json.loads((d / "waterfall.json").read_text(encoding="utf-8"))}
    R = {json.loads(l)["key"]: json.loads(l) for l in (d / "per_receipt.jsonl").open(encoding="utf-8") if l.strip()}
    return P, W, R


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--gate", default="total_label")
    ap.add_argument("--role", default="", help='e.g. "dev (gate designed here)" or "held-out"')
    args = ap.parse_args()
    root = ROOT / args.results
    out = root / f"gate_{args.gate}"
    P0, W0, R0 = load(root / "harness")
    P1, W1, R1 = load(out / "harness")

    tiers = {}
    for t in ("t2", "t3", "t4"):
        a, b = W0[t], W1[t]
        tiers[t] = {"model_errors": a["model_errors"], "caught_before": a["errors_caught"], "caught_after": b["errors_caught"],
                    "leaked_before": a["errors_leaked"], "leaked_after": b["errors_leaked"],
                    "false_flags_before": a["false_flags"], "false_flags_after": b["false_flags"]}
    pols = {}
    for k in POLICIES:
        a, b = P0[k], P1[k]
        pols[k] = {f: {"before": a[f], "after": b[f]} for f in
                   ("accepted_money_precision", "review_share", "cloud_sent_share", "cost_usd_per_1k", "leak_share", "auto_accept_share")}
    cases = []
    for key, r in R1.items():
        for t in ("t2", "t3", "t4"):
            new = sorted(set(r["flags"][t]) - set(R0[key]["flags"][t]))
            if new and not R0[key]["flags"][t]:          # the gate changed the verdict from pass to flagged
                cases.append({"key": key, "tier": t, "flags": new, "answer_right": bool(r[t]["money_ok"]), "pred_total": r[t]["pred"]["total"]})
    sha = hashlib.sha256((ROOT / "src" / "harness" / "verify.py").read_bytes()).hexdigest()
    res = {"results": args.results, "gate": args.gate, "role": args.role, "verify_py_sha256": sha, "n": P0["harness"]["n"],
           "tiers": tiers, "policies": pols, "changed_verdicts": cases,
           "caught_leaks": sum(1 for c in cases if not c["answer_right"]), "new_false_flags": sum(1 for c in cases if c["answer_right"])}
    (out / "comparison.json").write_text(json.dumps(res, indent=1), encoding="utf-8")

    pct = lambda v: "n/a" if v is None else f"{v * 100:.1f}%"
    md = [f"# Gate experiment: {args.gate} on {args.results} ({args.role or 'n/a'})", "",
          f"verify.py sha256 `{sha[:16]}…`; n = {res['n']}. Verdicts changed from pass to flagged: {len(cases)} "
          f"({res['caught_leaks']} were wrong answers that had leaked, {res['new_false_flags']} were right answers now flagged).", "",
          "| reader alone | model errors | caught before | caught after | leaked after | false flags before | after |", "|---|---|---|---|---|---|---|"]
    for t, v in tiers.items():
        md.append(f"| {t} | {v['model_errors']} | {v['caught_before']} | {v['caught_after']} | {v['leaked_after']} | {v['false_flags_before']} | {v['false_flags_after']} |")
    md += ["", "| policy | accepted correct | review | sent to cloud | USD / 1k | leak |", "|---|---|---|---|---|---|"]
    for k, v in pols.items():
        md.append(f"| {k} | {pct(v['accepted_money_precision']['before'])} → {pct(v['accepted_money_precision']['after'])} | "
                  f"{pct(v['review_share']['before'])} → {pct(v['review_share']['after'])} | "
                  f"{pct(v['cloud_sent_share']['before'])} → {pct(v['cloud_sent_share']['after'])} | "
                  f"{v['cost_usd_per_1k']['before']} → {v['cost_usd_per_1k']['after']} | {pct(v['leak_share']['before'])} → {pct(v['leak_share']['after'])} |")
    md += ["", "| key | tier | new flag | answer was |", "|---|---|---|---|"]
    md += [f"| {c['key']} | {c['tier']} | {', '.join(c['flags'])} | {'right (false flag)' if c['answer_right'] else 'wrong (leak caught)'} |" for c in cases]
    (out / "comparison.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
