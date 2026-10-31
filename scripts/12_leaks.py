"""12_leaks.py - Leak taxonomy (plan §C). Leak = a tier's answer wrong on date or
total while its flag list was empty (waterfall definition). Classes are assigned
by code, in this order: both_wrong, total_other_printed_amount,
total_digit_near_miss, total_other, date_day_month_swapped, date_other.

    python scripts/12_leaks.py --results results
    python scripts/12_leaks.py --results results_wild
Outputs: <results>/leaks/leaks.jsonl, <results>/leaks/leaks.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_NUM = re.compile(r"\d[\d,]*\.?\d*")


def ocr_amounts(lines: list[str]) -> set[float]:
    out = set()
    for l in lines:
        for tok in _NUM.findall(l):
            try:
                out.add(round(float(tok.replace(",", "")), 2))
            except ValueError:
                pass
    return out


def digit_near_miss(a: float, b: float) -> bool:
    sa, sb = f"{a:.2f}", f"{b:.2f}"
    if len(sa) == len(sb) and sum(x != y for x, y in zip(sa, sb)) == 1:
        return True
    return b != 0 and (abs(a / b - 10) < 1e-6 or abs(a / b - 0.1) < 1e-6)


def classify(pred: dict, gt: dict, lines: list[str]) -> tuple[str, str]:
    date_wrong = gt.get("date") is not None and pred.get("date") != gt["date"]
    total_wrong = gt.get("total") is not None and pred.get("total") != gt["total"]
    if date_wrong and total_wrong:
        return "both_wrong", ""
    if total_wrong:
        pt, gtot = pred.get("total"), gt["total"]
        if pt is not None and pt in ocr_amounts(lines) and pt != gtot:
            return "total_other_printed_amount", f"{pt:.2f}"
        if pt is not None and digit_near_miss(pt, gtot):
            return "total_digit_near_miss", f"{pt:.2f} vs {gtot:.2f}"
        return "total_other", f"{pt} vs {gtot}"
    pd, gd = pred.get("date"), gt["date"]
    if pd and gd and pd[:4] == gd[:4] and pd[5:7] == gd[8:10] and pd[8:10] == gd[5:7]:
        return "date_day_month_swapped", f"{pd} vs {gd}"
    return "date_other", f"{pd} vs {gd}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    args = ap.parse_args()
    root = ROOT / args.results
    schema = json.loads((root / "harness" / "per_receipt.schema.json").read_text(encoding="utf-8"))
    assert schema["schema_version"] == 1, "per_receipt schema changed; update 12_leaks.py"
    rows = [json.loads(l) for l in (root / "harness" / "per_receipt.jsonl").open(encoding="utf-8") if l.strip()]
    out = root / "leaks"
    out.mkdir(exist_ok=True)
    leaks = []
    for r in rows:
        lines = []
        f = root / "rapidocr" / f"{r['key']}.json"
        if f.exists():
            lines = json.loads(f.read_text(encoding="utf-8")).get("lines") or []
        for tier in ("t2", "t3", "t4"):
            ev = r[tier]
            if not ev["available"] or ev["money_ok"] is None or ev["money_ok"] or r["flags"][tier]:
                continue
            gt = {k: ev["correct"].get(k) for k in ()}  # placeholder, replaced below
            # ground truth is not stored in per_receipt; recover from pred/correct via the manifest
            leaks.append({"key": r["key"], "tier": tier, "pred": ev["pred"], "correct": ev["correct"], "lines": lines})
    # manifest for ground truth
    man_name = "sroie300.jsonl" if args.results == "results" else "wild200.jsonl"
    manifest = {json.loads(l)["key"]: json.loads(l) for l in (ROOT / "data" / "manifest" / man_name).open(encoding="utf-8") if l.strip()}
    counts: dict[str, dict[str, int]] = {}
    with (out / "leaks.jsonl").open("w", encoding="utf-8") as fh:
        for lk in leaks:
            gt = manifest[lk["key"]]["gt"]
            cls, note = classify(lk["pred"], gt, lk["lines"])
            counts.setdefault(lk["tier"], {}).setdefault(cls, 0)
            counts[lk["tier"]][cls] += 1
            fh.write(json.dumps({"key": lk["key"], "tier": lk["tier"], "pred": lk["pred"], "gt": gt, "class": cls,
                                 "note": note, "schema_version": 1}, ensure_ascii=False) + "\n")
    md = [f"# Leaks ({args.results}): wrong date/total that passed every code check", "",
          f"rows: {len(leaks)}", "", "| tier | class | n |", "|---|---|---|"]
    for tier, cs in sorted(counts.items()):
        for cls, n in sorted(cs.items(), key=lambda kv: -kv[1]):
            md.append(f"| {tier} | {cls} | {n} |")
    (out / "leaks.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
