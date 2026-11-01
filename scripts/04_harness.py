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
    local_only       T1, then T2 with the code checks, then review; never calls the cloud
    oracle           escalates exactly the receipts T1 gets wrong (upper bound)

The policies with code checks (harness, harness_ladder, local_only and their _solo variants) also
require T1's date to pass the date plausibility check before T1 is accepted (signal.date_ok, added
2026-10-31 after the poster: a T1 that is sure about a receipt dated in the future used to skip every
check). The router stays check-free by definition.

Tier-1 records are refreshed with the current rules (rules.refresh) when loaded, so a rules or
normalizer fix reaches the cached OCR reads.

Masking experiment (docs/plan-pii-mask.md): masking is a swap of the T3/T4 read folders, not a new
policy, e.g. --t3 pii/M1/gemini-lite --t4 pii/M1/gemini --keys results/pii/sample.json
--gates tags --jobs results/pii/M1/jobs.json --out results/pii/M1/harness.

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
from harness import rules, verify  # noqa: E402
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
GATES: tuple[str, ...] = ()                  # optional gates, from --gates ("total_label" in verify.py, "tags" in mask.py)


def t1_date_ok(rapid: dict | None, day_first: bool = True) -> bool:
    """T1's own date through the same plausibility window as the VLM answers (no ground truth)."""
    d = predicted_fields(rapid, day_first=day_first)["date"] if rapid else None
    return d is not None and not verify.check_date({"date": d}, today=ERA["today"], min_year=ERA["min_year"])


def vlm_flags(rec: dict | None, ocr_lines: list[str] | None, n_tags: int | None = None) -> list[str]:
    """n_tags: tags issued for this receipt's masked image (masking experiment); used only with --gates tags."""
    if rec is None:
        return ["UNAVAILABLE"]
    flags = verify.verify(rec, ocr_lines, today=ERA["today"], min_year=ERA["min_year"],
                          gates=tuple(g for g in GATES if g != "tags"))
    if "tags" in GATES:
        from harness.mask import check_tags
        flags += check_tags(rec, n_tags)
    return [f.name for f in flags]


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------
INF = float("inf")


def decide(row: dict, policy: str, params: dict | float) -> dict:
    """Return {'tier': accepted tier or 'review', 'path': [...tiers consulted], 'cost': float, 'latency_ms': int}.
    params: {'tau': float} for the rule policies, {'D': seconds, 'scale': float} for 'hedge'."""
    if not isinstance(params, dict):
        params = {"tau": float(params)}
    tau = float(params.get("tau", 0.9))
    t1, t2, t3, t4 = row["t1"], row["t2"], row["t3"], row["t4"]
    sig = row["signal"]
    path, cost, lat = [], 0.0, 0

    if policy == "hedge":
        # Plan §B: start T2 at t=0; if its (scaled) arrival is later than D, fire T3 at t=D.
        # First arrival with an empty flag list wins; all flagged -> review. T4 never called.
        D = float(params.get("D", 5.0))
        scale = float(params.get("scale", 1.0))
        t2_arr = ((t2["latency_ms"] or 0) / 1000.0) * scale if t2["available"] else INF
        fired = [("T2", t2_arr, t2, row["flags"]["t2"])]
        cloud_fired = t2_arr > D
        if cloud_fired:
            t3_arr = (D if D != INF else 0.0) + ((t3["latency_ms"] or 0) / 1000.0) if t3["available"] else INF
            fired.append(("T3", t3_arr, t3, row["flags"]["t3"]))
        fired.sort(key=lambda x: x[1])
        cost = sum((ev["cost"] or 0.0) for _, _, ev, _ in fired if ev["available"])
        path = [n for n, _, _, _ in fired]
        for name, arr, ev, flags in fired:
            if ev["available"] and not flags:
                return {"tier": name, "path": path, "cost": cost, "latency_ms": int(arr * 1000) if arr != INF else 0,
                        "latency_kind": "wall", "cloud_fired": cloud_fired}
        arrivals = [a for _, a, ev, _ in fired if ev["available"] and a != INF]
        return {"tier": "review", "path": path, "cost": cost, "latency_ms": int(max(arrivals) * 1000) if arrivals else 0,
                "latency_kind": "wall", "cloud_fired": cloud_fired}

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
    if policy in ("harness", "harness_ladder", "local_only"):
        local_ok = local_ok and sig.get("date_ok", True)       # policies with checks also check T1's date
    if policy == "oracle":
        take("T1", t1)
        if t1["money_ok"]:
            return {"tier": "T1", "path": path, "cost": cost, "latency_ms": lat}
        take("T3", t3)
        return {"tier": "T3", "path": path, "cost": cost, "latency_ms": lat}

    if policy == "local_only":
        # No cloud at all: T1 when its self-signal passes, else the local VLM with code checks, else review.
        take("T1", t1)
        if local_ok:
            return {"tier": "T1", "path": path, "cost": cost, "latency_ms": lat}
        take("T2", t2)
        if t2["available"] and not row["flags"]["t2"]:
            return {"tier": "T2", "path": path, "cost": cost, "latency_ms": lat}
        return {"tier": "review", "path": path, "cost": cost, "latency_ms": lat}

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


def summarize(rows: list[dict], policy: str, params: dict | float) -> dict:
    if not isinstance(params, dict):
        params = {"tau": float(params)}
    tau = params.get("tau")
    n = len(rows)
    accepted = 0
    acc_money_ok = 0
    acc_all_ok = 0
    leaked = 0
    review = 0
    cloud_fired = 0
    sent = 0              # receipts whose image reached a cloud tier (accepted there or not)
    tiers = {"T1": 0, "T2": 0, "T3": 0, "T4": 0}
    cost = 0.0
    costed = 0            # receipts whose whole decision path had results (cost is averaged over these only)
    lats = []
    for row in rows:
        d = decide(row, policy, params)
        cloud_fired += 1 if d.get("cloud_fired") else 0
        sent += 1 if any(t in ("T3", "T4") for t in d["path"]) else 0
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
        "policy": policy, "tau": tau, "params": params, "n": n,
        "cloud_fired_share": round(cloud_fired / n, 4) if policy == "hedge" else None,
        "latency_kind": "wall" if policy == "hedge" else "sequential_sum",
        "auto_accept_share": round(accepted / n, 4),
        "review_share": round(review / n, 4),
        "tier_share": {k: round(v / n, 4) for k, v in tiers.items()},
        "cloud_sent_share": round(sent / n, 4),                              # image left the machine
        "cloud_accepted_share": round((tiers["T3"] + tiers["T4"]) / n, 4),   # answer accepted from a cloud tier
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
    ap.add_argument("--gates", default="", help="optional gates, comma separated (total_label, tags)")
    ap.add_argument("--keys", default=None,
                    help="JSON with a 'keys' list (e.g. results/pii/sample.json): replay only these receipts; "
                         "the date window still comes from the full manifest")
    ap.add_argument("--jobs", default=None,
                    help="masking experiment jobs.json ({'receipts': {key: {'status', 'n_tags'}}}); "
                         "gives the tags gate its n_tags and checks refused receipts have no cloud read")
    args = ap.parse_args()
    global GATES
    GATES = tuple(g for g in args.gates.split(",") if g)
    keys = set(json.loads((ROOT / args.keys).read_text(encoding="utf-8"))["keys"]) if args.keys else None
    jobs = json.loads((ROOT / args.jobs).read_text(encoding="utf-8"))["receipts"] if args.jobs else {}

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
    if keys is not None:
        missing = keys - {it["key"] for it in manifest}
        assert not missing, f"--keys holds receipts not in {args.manifest}: {sorted(missing)[:5]}"
        manifest = [it for it in manifest if it["key"] in keys]
        print(f"--keys: replaying {len(manifest)} receipts")
    for k, j in jobs.items():
        if j.get("status") == "refused":
            assert k not in R["t3"] and k not in R["t4"], f"{k} was refused by the masker but has a cloud read"

    rows = []
    for item in manifest:
        key, gt = item["key"], item["gt"]
        df = item.get("day_first", True)
        rapid, tess = rules.refresh(R["t1"].get(key), df), rules.refresh(R["t1b"].get(key), df)
        # Independent witness text = union of both traditional readers' lines.
        ocr_lines = ((rapid or {}).get("lines") or []) + ((tess or {}).get("lines") or [])
        ocr_lines = ocr_lines or None
        row = {
            "key": key,
            "day_first": df,
            "t1": tier_eval(rapid, gt, df),
            "t1b": tier_eval(tess, gt, df),
            "t2": tier_eval(R["t2"].get(key), gt, df),
            "t3": tier_eval(R["t3"].get(key), gt, df),
            "t4": tier_eval(R["t4"].get(key), gt, df),
            "signal": {**local_signal(rapid, tess, df), "date_ok": t1_date_ok(rapid, df)},
            "flags": {t: vlm_flags(R[t].get(key), ocr_lines, None if t == "t2" else jobs.get(key, {}).get("n_tags"))
                      for t in ("t2", "t3", "t4")},
        }
        rows.append(row)

    out = Path(args.out) if args.out else ROOT_RESULTS / "harness"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "per_receipt.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    policies = [summarize(rows, p, {"tau": args.tau}) for p in
                ("all_local", "all_qwen", "all_lite", "all_strong", "oracle", "router", "harness", "harness_ladder",
                 "router_solo", "harness_solo", "harness_ladder_solo", "local_only", "local_only_solo")]
    sweep = [summarize(rows, p, {"tau": tau}) for p in ("router", "harness", "harness_ladder", "router_solo", "harness_solo", "harness_ladder_solo", "local_only", "local_only_solo")
             for tau in (0.0, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.93, 0.95, 0.97, 0.99, 1.01)]
    falls = [waterfall(rows, t) for t in ("t2", "t3", "t4")]

    (out / "policies.json").write_text(json.dumps(policies, indent=1), encoding="utf-8")
    (out / "tau_sweep.json").write_text(json.dumps(sweep, indent=1), encoding="utf-8")
    (out / "waterfall.json").write_text(json.dumps(falls, indent=1), encoding="utf-8")
    pct = lambda v: "n/a" if v is None else f"{v*100:.1f}%"   # noqa: E731
    (out / "per_receipt.schema.json").write_text(json.dumps({
        "schema_version": 1,
        "required_row_keys": ["key", "t1", "t1b", "t2", "t3", "t4", "signal", "flags"],
        "optional_row_keys": ["day_first"],
        "tier_keys": ["pred", "correct", "money_ok", "all_ok", "cost", "latency_ms", "available"],
        "signal_keys": ["agree", "conf", "complete", "date_ok"],
    }, indent=1), encoding="utf-8")

    # Plan §B: latency-aware hedging, D seconds x local latency scale.
    hedge_out = out.parent / "hedge"
    hedge_out.mkdir(parents=True, exist_ok=True)
    hedge = [dict(summarize(rows, "hedge", {"D": D, "scale": sc}), D=D, scale=sc)
             for sc in (1.0, 0.25) for D in (0.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, INF)]
    (hedge_out / "curve.json").write_text(json.dumps(hedge, indent=1, default=str), encoding="utf-8")
    hl = ["# Hedge policy: start local VLM, fire Flash-Lite at D seconds if the local answer is not in", "",
          "| scale | D (s) | cloud fired | accepted precision | review | leak | USD / 1k | wait p50 (ms) |", "|---|---|---|---|---|---|---|---|"]
    for h in hedge:
        hl.append(f"| {h['scale']} | {'inf' if h['D'] == INF else int(h['D'])} | {pct(h['cloud_fired_share'])} | {pct(h['accepted_money_precision'])} | "
                  f"{pct(h['review_share'])} | {pct(h['leak_share'])} | {h['cost_usd_per_1k']} | {h['latency_ms_median']} |")
    (hedge_out / "summary.md").write_text("\n".join(hl) + "\n", encoding="utf-8")

    lines = [f"# Routing policies (tau = {args.tau}; date+total exact match)", "",
             "Tier columns = where the receipt was accepted. Sent to cloud = the image reached a cloud tier (accepted there or not).", "",
             "| policy | auto-accept | review | sent to cloud | T1 | T2 | T3 | T4 | accepted precision (date+total) | leak | USD / 1k | latency med (ms) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in policies:
        ts = s["tier_share"]
        lines.append(f"| {s['policy']} | {pct(s['auto_accept_share'])} | {pct(s['review_share'])} | {pct(s['cloud_sent_share'])} | {pct(ts['T1'])} | {pct(ts['T2'])} | "
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
