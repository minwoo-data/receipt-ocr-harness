"""03_score.py - Exact-match scoring of every engine against ground truth.

Scoring is deterministic code on normalized values (see harness.normalize);
no model grades anything here. A ground-truth field that is null is skipped
for that receipt (one SROIE receipt has an empty total).

Usage:
    python scripts/03_score.py                       # all engines found under results/
    python scripts/03_score.py --engines rapidocr gemini-lite

Outputs:
    results/scores/<engine>.jsonl    per-receipt correctness + latency + cost
    results/scores/summary.md        per-engine table
    results/scores/summary.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from harness.normalize import norm_company, norm_date, norm_total  # noqa: E402

FIELDS = ("company", "date", "total")


def load_manifest(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8") as fh:
        return {r["key"]: r for r in (json.loads(l) for l in fh if l.strip())}


def predicted_fields(rec: dict) -> dict:
    """Map either record shape onto the three scored fields."""
    if "fields" in rec:                       # tier 1 (text + rules)
        f = rec["fields"]
        return {"company": norm_company(f.get("company")),
                "date": norm_date(f.get("date"), day_first=True),
                "total": norm_total(f.get("total"))}
    data = rec.get("data") or {}             # VLM tiers
    return {"company": norm_company(data.get("vendor")),
            "date": norm_date(data.get("date"), day_first=True),
            "total": norm_total(data.get("total"))}


def score_engine(engine: str, manifest: dict[str, dict], out_dir: Path) -> dict | None:
    res_dir = ROOT / "results" / engine
    files = sorted(res_dir.glob("*.json"))
    if not files:
        return None
    rows = []
    for f in files:
        rec = json.loads(f.read_text(encoding="utf-8"))
        key = rec.get("key") or f.stem
        gt = manifest[key]["gt"]
        pred = predicted_fields(rec)
        correct = {}
        for fld in FIELDS:
            if gt[fld] is None:
                correct[fld] = None               # unscorable
            else:
                correct[fld] = (pred[fld] == gt[fld])
        scored = [c for c in correct.values() if c is not None]
        rows.append({
            "key": key,
            "pred": pred,
            "gt": gt,
            "correct": correct,
            "all_correct": all(scored) if scored else None,
            "latency_ms": rec.get("latency_ms"),
            "cost_usd": rec.get("cost_usd"),
            "provider": rec.get("provider"),
            "engine_model": rec.get("engine"),
            "parsed": (rec.get("data") is not None) if "data" in rec else True,
            "rule_reasons": rec.get("rule_reasons"),
            "sanitizer_warnings": (rec.get("sanitizer") or {}).get("warnings"),
        })
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{engine}.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    n = len(rows)
    acc = {}
    for fld in FIELDS:
        scored = [r["correct"][fld] for r in rows if r["correct"][fld] is not None]
        acc[fld] = round(sum(scored) / len(scored), 4) if scored else None
    all_ok = [r["all_correct"] for r in rows if r["all_correct"] is not None]
    lat = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    costs = [r["cost_usd"] for r in rows if isinstance(r["cost_usd"], (int, float))]
    return {
        "engine": engine,
        "n": n,
        "acc": acc,
        "all_three": round(sum(all_ok) / len(all_ok), 4) if all_ok else None,
        "parsed_share": round(sum(1 for r in rows if r["parsed"]) / n, 4),
        "latency_ms_median": int(statistics.median(lat)) if lat else None,
        "latency_ms_p90": int(sorted(lat)[int(len(lat) * 0.9)]) if lat else None,
        "cost_usd_per_1k": round(sum(costs) / len(costs) * 1000, 3) if costs else 0.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/manifest/sroie300.jsonl")
    ap.add_argument("--engines", nargs="*", default=None)
    args = ap.parse_args()
    manifest = load_manifest(ROOT / args.manifest)
    out_dir = ROOT / "results" / "scores"
    engines = args.engines or sorted(p.name for p in (ROOT / "results").iterdir()
                                     if p.is_dir() and p.name not in ("scores", "figures", "raw_responses"))
    summaries = [s for s in (score_engine(e, manifest, out_dir) for e in engines) if s]

    lines = ["# Engine scores (exact match after normalization)", "",
             "| engine | n | company | date | total | all 3 | parsed | latency med / p90 (ms) | USD per 1k |",
             "|---|---|---|---|---|---|---|---|---|"]
    for s in summaries:
        a = s["acc"]
        pct = lambda v: "n/a" if v is None else f"{v*100:.1f}%"
        lines.append(f"| {s['engine']} | {s['n']} | {pct(a['company'])} | {pct(a['date'])} | {pct(a['total'])} | "
                     f"{pct(s['all_three'])} | {pct(s['parsed_share'])} | {s['latency_ms_median']} / {s['latency_ms_p90']} | "
                     f"{s['cost_usd_per_1k']} |")
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summaries, indent=1), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
