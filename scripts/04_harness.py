"""04_harness.py - Offline simulation of routing policies and the verification
harness over the collected engine outputs. No API calls: everything here is
replayed from results/<engine>/*.json, so the whole analysis is reproducible.

Tiers (results folders):
    T1  rapidocr (+ tesseract as the second traditional reader)   local, $0
    T2  qwen      (qwen2.5vl:3b via Ollama)                       local, $0
    T3  gemini-lite (gemini-3.1-flash-lite)                        cloud, cheap
    T4  gemini      (gemini-3.6-flash)                             cloud, strong

Policies:
    all_local        accept T1 for every receipt
    all_qwen         accept T2 for every receipt (if available)
    all_lite         accept T3 for every receipt
    all_strong       accept T4 for every receipt
    router(tau)      T1 accepted when its own signals pass (both traditional
                     readers agree on date+total, mean conf >= tau), else T3
                     accepted blindly
    harness(tau)     same escalation, but every accepted VLM answer must pass
                     the code checks (verify.py); a flagged T3 answer escalates
                     to T4; a flagged T4 answer goes to human review. Auto-accept
                     only with zero flags. Model confidence is never consulted.
    harness_ladder   adds T2 between T1 and T3 (local VLM before any cloud call)
    oracle           escalates exactly the receipts T1 gets wrong (upper bound)

Outputs: results/harness/policies.md, policies.json, tau_sweep.json,
         waterfall.json, per_receipt.jsonl
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from harness import verify  # noqa: E402
from harness.scoring import all_fields_ok, correct_fields, money_fields_ok, predicted_fields  # noqa: E402

TODAY = date(2026, 10, 31)
REVIEW_COST_USD = 0.0      # human review is reported as a share, not priced


ROOT_RESULTS = ROOT / "results"


def load_dir(name: str) -> dict[str, dict]:
    d = ROOT_RESULTS / name
    if not d.exists():
        return {}
    out = {}
    for f in d.glob("*.json"):
        rec = json.loads(f.read_text(encoding="utf-8"))
        out[rec.get("key") or f.stem] = rec
    return out


def load_manifest(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


# ---------------------------------------------------------------------------
# Per-receipt evaluation of each tier
# ---------------------------------------------------------------------------
def tier_eval(rec: dict | None, gt: dict, day_first: bool = True) -> dict:
    pred = predicted_fields(rec, day_first=day_first)
    corr = correct_fields(pred, gt)
    return {"pred": pred, "correct": corr, "money_ok": money_fields_ok(corr), "all_ok": all_fields_ok(corr),
            "cost": (rec or {}).get("cost_usd") or 0.0, "latency_ms": (rec or {}).get("latency_ms") or 0,
            "available": rec is not None}


def local_signal(rapid: dict | None, tess: dict | None, day_first: bool = True) -> dict:
    """Tier-1 self-signals (no ground truth): did both traditional readers
    produce the same date and total, and how confident was RapidOCR."""
    if not rapid:
        return {"agree": False, "conf": 0.0, "complete": False}
    rp = predicted_fields(rapid, day_first=day_first)
    tp = predicted_fields(tess, day_first=day_first) if tess else {"date": None, "total": None}
    complete = rp["date"] is not None and rp["total"] is not None and not (rapid.get("rule_reasons") or [])
    agree = complete and rp["date"] == tp["date"] and rp["total"] == tp["total"]
    return {"agree": bool(agree), "conf": float(rapid.get("mean_conf") or 0.0), "complete": bool(complete)}


ERA = {"today": TODAY, "min_year": None}     # set from the manifest's ground-truth years in main()


def vlm_flags(rec: dict | None, ocr_lines: list[str] | None) -> list[str]:
    if rec is None:
        return ["UNAVAILABLE"]
    return [f.name for f in verify.verify(rec, ocr_lines, today=ERA["today"], min_year=ERA["min_year"])]


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------
def decide(row: dict, policy: str, tau: float) -> dict:
    """Return {'tier': accepted tier or 'review', 'path': [...tiers consulted], 'cost': float, 'latency_ms': int}."""
    t1, t2, t3, t4 = row["t1"], row["t2"], row["t3"], row["t4"]
    sig = row["signal"]
    path, cost, lat = [], 0.0, 0

    def take(tier_name, ev):
        nonlocal cost, lat
        path.append(tier_name)
        cost += ev["cost"] or 0.0
        lat += ev["latency_ms"] or 0

    if policy == "all_local":
        take("T1", t1); return {"tier": "T1", "path": path, "cost": cost, "latency_ms": lat}
    if policy == "all_qwen":
        take("T2", t2); return {"tier": "T2" if t2["available"] else "review", "path": path, "cost": cost, "latency_ms": lat}
    if policy == "all_lite":
        take("T3", t3); return {"tier": "T3" if t3["available"] else "review", "path": path, "cost": cost, "latency_ms": lat}
    if policy == "all_strong":
        take("T4", t4); return {"tier": "T4" if t4["available"] else "review", "path": path, "cost": cost, "latency_ms": lat}

    # Two flavours of the tier-1 self-signal: "agree" needs both traditional
    # readers to produce the same date and total; "solo" trusts RapidOCR's own
    # completeness and confidence. Policies ending in _solo use the latter.
    solo = policy.endswith("_solo")
    policy = policy[:-5] if solo else policy
    local_ok = (sig["complete"] if solo else sig["agree"]) and sig["conf"] >= tau
    if policy == "oracle":
        take("T1", t1)
        if t1["money_ok"]:
            return {"tier": "T1", "path": path, "cost": cost, "latency_ms": lat}
        take("T3", t3)
        return {"tier": "T3", "path": path, "cost": cost, "latency_ms": lat}

    if policy == "router":
        take("T1", t1)
        if local_ok:
            return {"tier": "T1", "path": path, "cost": cost, "latency_ms": lat}
        take("T3", t3)
        return {"tier": "T3" if t3["available"] else "review", "path": path, "cost": cost, "latency_ms": lat}

    if policy in ("harness", "harness_ladder"):
        take("T1", t1)
        if local_ok:
            return {"tier": "T1", "path": path, "cost": cost, "latency_ms": lat}
        if policy == "harness_ladder" and t2["available"]:
            take("T2", t2)
            if not row["flags"]["t2"]:
                return {"tier": "T2", "path": path, "cost": cost, "latency_ms": lat}
        take("T3", t3)
        if t3["available"] and not row["flags"]["t3"]:
            return {"tier": "T3", "path": path, "cost": cost, "latency_ms": lat}
        take("T4", t4)
        if t4["available"] and not row["flags"]["t4"]:
            return {"tier": "T4", "path": path, "cost": cost, "latency_ms": lat}
        return {"tier": "review", "path": path, "cost": cost, "latency_ms": lat}
    raise ValueError(policy)


def summarize(rows: list[dict], policy: str, tau: float) -> dict:
    n = len(rows)
    accepted = 0
    acc_money_ok = 0
    acc_all_ok = 0
    leaked = 0
    review = 0
    tiers = {"T1": 0, "T2": 0, "T3": 0, "T4": 0}
    cost = 0.0
    costed = 0            # receipts whose whole decision path had results (cost is averaged over these only)
    lats = []
    for row in rows:
        d = decide(row, policy, tau)
        if all(row[t.lower()]["available"] for t in d["path"]):
            cost += d["cost"]
            costed += 1
            lats.append(d["latency_ms"])
        if d["tier"] == "review":
            review += 1
            continue
        tiers[d["tier"]] += 1
        accepted += 1
        ev = row[d["tier"].lower()]
        if ev["money_ok"]:
            acc_money_ok += 1
        else:
            leaked += 1
        if ev["all_ok"]:
            acc_all_ok += 1
    return {
        "policy": policy, "tau": tau, "n": n,
        "auto_accept_share": round(accepted / n, 4),
        "review_share": round(review / n, 4),
        "tier_share": {k: round(v / n, 4) for k, v in tiers.items()},
        "cloud_share": round((tiers["T3"] + tiers["T4"]) / n, 4),
        "accepted_money_precision": round(acc_money_ok / accepted, 4) if accepted else None,
        "accepted_all3_precision": round(acc_all_ok / accepted, 4) if accepted else None,
        "leak_share": round(leaked / n, 4),                 # wrong date/total that reached auto-accept
        "cost_usd_per_1k": round(cost / costed * 1000, 3) if costed else None,
        "costed_receipts": costed,
        "latency_ms_median": int(statistics.median(lats)) if lats else 0,
    }


def waterfall(rows: list[dict], tier: str) -> dict:
    """For one VLM tier: model-alone errors -> how many the code checks flagged."""
    avail = [r for r in rows if r[tier]["available"]]
    errors = [r for r in avail if not r[tier]["money_ok"]]
    flagged = [r for r in avail if r["flags"][tier]]
    caught = [r for r in errors if r["flags"][tier]]
    false_flags = [r for r in flagged if r[tier]["money_ok"]]
    by_flag: dict[str, int] = {}
    for r in flagged:
        for fl in r["flags"][tier]:
            by_flag[fl] = by_flag.get(fl, 0) + 1
    return {
        "tier": tier, "n": len(avail),
        "model_errors": len(errors),
        "flagged": len(flagged),
        "errors_caught": len(caught),
        "errors_leaked": len(errors) - len(caught),
        "false_flags": len(false_flags),
        "verifier_recall": round(len(caught) / len(errors), 4) if errors else None,
        "verifier_precision": round((len(flagged) - len(false_flags)) / len(flagged), 4) if flagged else None,
        "flag_counts": dict(sorted(by_flag.items(), key=lambda kv: -kv[1])),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/manifest/sroie300.jsonl")
    ap.add_argument("--t1", default="rapidocr")
    ap.add_argument("--t1b", default="tesseract")
    ap.add_argument("--t2", default="qwen")
    ap.add_argument("--t3", default="gemini-lite")
    ap.add_argument("--t4", default="gemini")
    ap.add_argument("--tau", type=float, default=0.9)
    ap.add_argument("--results", default="results", help="results root (e.g. results_wild for the WildReceipt run)")
    ap.add_argument("--out", default=None, help="output folder; default <results>/harness")
    args = ap.parse_args()

    manifest = load_manifest(ROOT / args.manifest)
    global ROOT_RESULTS
    ROOT_RESULTS = ROOT / args.results
    # Date plausibility window = the era of the dataset (max GT year end, min GT year).
    years = sorted(int(it["gt"]["date"][:4]) for it in manifest if it.get("gt", {}).get("date"))
    if years:
        ERA["today"] = date(years[-1], 12, 31)
        ERA["min_year"] = years[0]
    print("date window:", ERA)
    R = {k: load_dir(v) for k, v in (("t1", args.t1), ("t1b", args.t1b), ("t2", args.t2), ("t3", args.t3), ("t4", args.t4))}
    print({k: len(v) for k, v in R.items()})

    rows = []
    for item in manifest:
        key, gt = item["key"], item["gt"]
        rapid, tess = R["t1"].get(key), R["t1b"].get(key)
        # Independent witness text = union of both traditional readers' lines.
        ocr_lines = ((rapid or {}).get("lines") or []) + ((tess or {}).get("lines") or [])
        ocr_lines = ocr_lines or None
        df = item.get("day_first", True)
        row = {
            "key": key,
            "t1": tier_eval(rapid, gt, df),
            "t1b": tier_eval(tess, gt, df),
            "t2": tier_eval(R["t2"].get(key), gt, df),
            "t3": tier_eval(R["t3"].get(key), gt, df),
            "t4": tier_eval(R["t4"].get(key), gt, df),
            "signal": local_signal(rapid, tess, df),
            "flags": {t: vlm_flags(R[t].get(key), ocr_lines) for t in ("t2", "t3", "t4")},
        }
        rows.append(row)

    out = Path(args.out) if args.out else ROOT_RESULTS / "harness"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "per_receipt.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    policies = [summarize(rows, p, args.tau) for p in
                ("all_local", "all_qwen", "all_lite", "all_strong", "oracle", "router", "harness", "harness_ladder",
                 "router_solo", "harness_solo", "harness_ladder_solo")]
    sweep = [summarize(rows, p, tau) for p in ("router", "harness", "harness_ladder", "router_solo", "harness_solo", "harness_ladder_solo")
             for tau in (0.0, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.93, 0.95, 0.97, 0.99, 1.01)]
    falls = [waterfall(rows, t) for t in ("t2", "t3", "t4")]

    (out / "policies.json").write_text(json.dumps(policies, indent=1), encoding="utf-8")
    (out / "tau_sweep.json").write_text(json.dumps(sweep, indent=1), encoding="utf-8")
    (out / "waterfall.json").write_text(json.dumps(falls, indent=1), encoding="utf-8")

    pct = lambda v: "n/a" if v is None else f"{v*100:.1f}%"
    lines = [f"# Routing policies (tau = {args.tau}; date+total exact match)", "",
             "| policy | auto-accept | review | T1 | T2 | T3 | T4 | accepted precision (date+total) | leak | USD / 1k | latency med (ms) |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in policies:
        ts = s["tier_share"]
        lines.append(f"| {s['policy']} | {pct(s['auto_accept_share'])} | {pct(s['review_share'])} | {pct(ts['T1'])} | {pct(ts['T2'])} | "
                     f"{pct(ts['T3'])} | {pct(ts['T4'])} | {pct(s['accepted_money_precision'])} | {pct(s['leak_share'])} | "
                     f"{s['cost_usd_per_1k']} | {s['latency_ms_median']} |")
    lines += ["", "# Verification waterfall (per VLM tier)", "",
              "| tier | n | model errors | flagged | caught | leaked | false flags | recall | precision | top flags |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for w in falls:
        top = ", ".join(f"{k}:{v}" for k, v in list(w["flag_counts"].items())[:5])
        lines.append(f"| {w['tier']} | {w['n']} | {w['model_errors']} | {w['flagged']} | {w['errors_caught']} | {w['errors_leaked']} | "
                     f"{w['false_flags']} | {pct(w['verifier_recall'])} | {pct(w['verifier_precision'])} | {top} |")
    (out / "policies.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
