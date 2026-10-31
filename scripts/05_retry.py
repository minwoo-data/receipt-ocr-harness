"""05_retry.py - Targeted re-read of flagged receipts: blind vs guided prompt.

For every receipt the code checks flagged (verify.py, with the traditional
OCR text as witness), ask the SAME model to read again with the suspect field
named, in two ways:

    blind    names the field, shows no previous values
    guided   production style: shows the previous values and the failed
             check, never a target value for the suspect field

Then code (not the model) scores: did the retry fix a wrong answer, keep a
right one, or break a right one (anchoring)? The candidate finally kept is
chosen by code: the retry answer wins only if it passes more checks.

Usage:
    python scripts/05_retry.py --engine gemini-lite
Outputs:
    results/retry/<engine>/<key>.<mode>.json
    results/retry/<engine>_summary.md / .json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from harness import verify  # noqa: E402
from harness.engines import vlm  # noqa: E402
from harness.schema import retry_prompt_blind, retry_prompt_guided  # noqa: E402
from harness.scoring import correct_fields, money_fields_ok, predicted_fields  # noqa: E402

TODAY = date(2026, 10, 31)
CHAINS = {
    "gemini-lite": (("gemini", "gemini-3.1-flash-lite"),),
    "gemini": (("gemini", "gemini-3.6-flash"),),
    "gemini-lite35": (("gemini", "gemini-3.5-flash-lite"),),
}


def load(dirname: str) -> dict[str, dict]:
    d = ROOT / "results" / dirname
    return {r.get("key") or f.stem: r for f in d.glob("*.json") for r in [json.loads(f.read_text(encoding="utf-8"))]} if d.exists() else {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="gemini-lite")
    ap.add_argument("--manifest", default="data/manifest/sroie300.jsonl")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    manifest = {json.loads(l)["key"]: json.loads(l) for l in (ROOT / args.manifest).open(encoding="utf-8") if l.strip()}
    base = load(args.engine)
    rapid, tess = load("rapidocr"), load("tesseract")
    out_dir = ROOT / "results" / "retry" / args.engine
    out_dir.mkdir(parents=True, exist_ok=True)

    flagged = []
    for key, rec in base.items():
        lines = ((rapid.get(key) or {}).get("lines") or []) + ((tess.get(key) or {}).get("lines") or [])
        flags = verify.verify(rec, lines or None, today=TODAY)
        if flags:
            flagged.append((key, rec, flags, lines))
    if args.limit:
        flagged = flagged[: args.limit]
    print(f"{args.engine}: {len(flagged)} flagged receipts of {len(base)}")

    rows = []
    for key, rec, flags, lines in flagged:
        field = verify.suspect_field(flags) or "total"
        reason = "; ".join(f"{f.name}: {f.detail}" for f in flags)[:300]
        gt = manifest[key]["gt"]
        df = manifest[key].get("day_first", True)
        before = predicted_fields(rec, day_first=df)
        before_ok = money_fields_ok(correct_fields(before, gt))
        row = {"key": key, "field": field, "flags": [f.name for f in flags], "before_ok": before_ok, "before": before}
        for mode in ("blind", "guided"):
            path = out_dir / f"{key}.{mode}.json"
            if path.exists():
                res = json.loads(path.read_text(encoding="utf-8"))
            else:
                prompt = retry_prompt_blind(field) if mode == "blind" else retry_prompt_guided(field, rec.get("data") or {}, reason)
                res = vlm.run_cloud_chain(ROOT / manifest[key]["image"], chain=CHAINS[args.engine], prompt=prompt)
                if res.get("provider") == "none":
                    print(f"  {key} {mode}: all providers failed, skipping")
                    continue
                res["key"] = key
                path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            after = predicted_fields(res, day_first=df)
            after_ok = money_fields_ok(correct_fields(after, gt))
            after_flags = [f.name for f in verify.verify(res, lines or None, today=TODAY)]
            # Code picks the kept candidate: fewer flags wins; ties keep the original.
            kept_retry = len(after_flags) < len(flags)
            row[mode] = {"after_ok": after_ok, "after_flags": after_flags, "kept_retry": kept_retry,
                         "kept_ok": after_ok if kept_retry else before_ok, "after": after,
                         "cost_usd": res.get("cost_usd")}
        rows.append(row)
        print(f"  {key} field={field} before_ok={before_ok} blind={row.get('blind', {}).get('after_ok')} guided={row.get('guided', {}).get('after_ok')}")

    summary = {"engine": args.engine, "n_flagged": len(rows)}
    for mode in ("blind", "guided"):
        have = [r for r in rows if mode in r]
        summary[mode] = {
            "n": len(have),
            "fixed": sum(1 for r in have if r["before_ok"] is False and r[mode]["after_ok"]),
            "broke": sum(1 for r in have if r["before_ok"] and r[mode]["after_ok"] is False),
            "unchanged_wrong": sum(1 for r in have if r["before_ok"] is False and r[mode]["after_ok"] is False),
            "kept_retry": sum(1 for r in have if r[mode]["kept_retry"]),
            "kept_ok": sum(1 for r in have if r[mode]["kept_ok"]),
            "flags_cleared": sum(1 for r in have if not r[mode]["after_flags"]),
        }
    (ROOT / "results" / "retry" / f"{args.engine}_summary.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    lines_md = [f"# Targeted retry on flagged receipts: {args.engine}", "", f"flagged: {len(rows)}", "",
                "| mode | n | fixed wrong->right | broke right->wrong | still wrong | flags cleared | code kept retry | kept answer correct |",
                "|---|---|---|---|---|---|---|---|"]
    for mode in ("blind", "guided"):
        s = summary[mode]
        lines_md.append(f"| {mode} | {s['n']} | {s['fixed']} | {s['broke']} | {s['unchanged_wrong']} | {s['flags_cleared']} | {s['kept_retry']} | {s['kept_ok']} |")
    (ROOT / "results" / "retry" / f"{args.engine}_summary.md").write_text("\n".join(lines_md) + "\n", encoding="utf-8")
    print("\n".join(lines_md))


if __name__ == "__main__":
    main()
