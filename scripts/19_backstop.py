"""19_backstop.py - What catches the errors that pass every code check? (offline, no API calls)

Replayed from <results>/harness/per_receipt.jsonl with the same decide() as 04_harness.py, tau = 0.9.
A leak is an auto-accepted answer whose date or total is wrong (the policies' leak_share).

Backstop 1, random audit: a person re-keys a random p% of auto-accepted receipts.
    Exact expectation (sampling without replacement): caught = k * leaks / accepted, k = round(p * accepted).
    P(audit finds at least one leak) is hypergeometric. The audit's main job is to estimate the leak
    rate, not to fix leaks: it fixes about p of them.
Backstop 2, amount-ranked re-check (cloud mode only): the top X% of auto-accepted receipts by the
    accepted total (no answer key needed to rank) are re-read by T4 (Gemini 3.6 Flash, cached read).
    If T4's date or total differs from the accepted answer, the receipt goes to human review.
    Receipts already accepted at T4 are not re-checked (T4 cannot check itself).
    Reported: leaks caught, correct answers wrongly sent to review, extra T4 cost, extra images sent
    to the cloud, and the share of the misstated amount covered (sum over leaks of |accepted total - true
    total|; a date-only leak misstates nothing).

    python scripts/19_backstop.py --results results
    python scripts/19_backstop.py --results results_wild --manifest data/manifest/wild200.jsonl
Outputs: <results>/backstop/summary.json, <results>/backstop/summary.md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("harness04", ROOT / "scripts" / "04_harness.py")
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)

AUDIT_P = (0.02, 0.05, 0.10)
RECHECK_X = (0.05, 0.10, 0.20, 0.30, 1.00)
TAU = 0.9


def load_rows(results: Path) -> list[dict]:
    with (results / "harness" / "per_receipt.jsonl").open(encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def accepted_view(rows: list[dict], policy: str) -> list[dict]:
    """One entry per auto-accepted receipt: tier, accepted answer, right or wrong, path."""
    out = []
    for r in rows:
        d = H.decide(r, policy, {"tau": TAU})
        if d["tier"] == "review":
            continue
        ev = r[d["tier"].lower()]
        out.append({"key": r["key"], "tier": d["tier"], "path": d["path"], "pred": ev["pred"], "right": bool(ev["money_ok"])})
    return out


def p_at_least_one(n: int, leaks: int, k: int) -> float:
    """Hypergeometric: P(a sample of k from n, with `leaks` bad items, contains >= 1 bad)."""
    if leaks == 0 or k == 0:
        return 0.0
    if n - leaks < k:
        return 1.0
    return 1.0 - comb(n - leaks, k) / comb(n, k)


def random_audit(acc: list[dict], n: int) -> list[dict]:
    leaks = sum(1 for a in acc if not a["right"])
    out = []
    for p in AUDIT_P:
        k = round(p * len(acc))
        exp_caught = k * leaks / len(acc) if acc else 0.0
        out.append({"p": p, "audited": k, "audited_per_1k": round(k / n * 1000, 1),
                    "expected_leaks_caught": round(exp_caught, 2),
                    "share_of_leaks_caught": round(exp_caught / leaks, 4) if leaks else None,
                    "p_find_at_least_one": round(p_at_least_one(len(acc), leaks, k), 4)})
    return out


def misstated(a: dict, gt_total: dict[str, float]) -> float:
    p, g = a["pred"].get("total"), gt_total.get(a["key"])
    return round(abs(p - g), 2) if p is not None and g is not None else (g or 0.0)


def amount_recheck(rows: list[dict], acc: list[dict], n: int, gt_total: dict[str, float]) -> list[dict]:
    by_key = {r["key"]: r for r in rows}
    # Rank by the accepted total (what production would see); a missing total ranks last.
    ranked = sorted(acc, key=lambda a: -(a["pred"].get("total") if a["pred"].get("total") is not None else float("-inf")))
    leaks = [a for a in acc if not a["right"]]
    leak_value = sum(misstated(a, gt_total) for a in leaks)
    out = []
    for x in RECHECK_X:
        top = ranked[:round(x * len(acc))]
        caught = false_flag = rechecked = newly_sent = 0
        missed_unchecked = 0
        cost = 0.0
        caught_value = 0.0
        for a in top:
            if a["tier"] == "T4":
                if not a["right"]:
                    missed_unchecked += 1
                continue
            t4 = by_key[a["key"]]["t4"]
            if not t4["available"]:
                continue
            rechecked += 1
            cost += t4["cost"] or 0.0
            newly_sent += 0 if any(t in ("T3", "T4") for t in a["path"]) else 1
            p, q = a["pred"], t4["pred"]
            differs = p.get("date") != q.get("date") or p.get("total") != q.get("total")
            if differs and not a["right"]:
                caught += 1
                caught_value += misstated(a, gt_total)
            elif differs:
                false_flag += 1
        out.append({"x": x, "considered": len(top), "rechecked": rechecked, "leaks_caught": caught,
                    "leaks_total": len(leaks), "false_flags": false_flag,
                    "extra_review_per_1k": round((caught + false_flag) / n * 1000, 1),
                    "extra_usd_per_1k": round(cost / n * 1000, 3),
                    "extra_cloud_sent_share": round(newly_sent / n, 4),
                    "misstated_total": round(leak_value, 2),
                    "misstated_covered_share": round(caught_value / leak_value, 4) if leak_value else None,
                    "leaks_in_top_accepted_at_T4": missed_unchecked})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--manifest", default="data/manifest/sroie300.jsonl")
    args = ap.parse_args()
    res = ROOT / args.results
    rows = load_rows(res)
    n = len(rows)
    with (ROOT / args.manifest).open(encoding="utf-8") as fh:
        gt_total = {it["key"]: (it.get("gt") or {}).get("total") for it in map(json.loads, filter(str.strip, fh))}

    pol = {p["policy"]: p for p in json.loads((res / "harness" / "policies.json").read_text(encoding="utf-8"))}
    summary = {"n": n, "tau": TAU, "modes": {}}
    for mode, policy in (("cloud", "harness"), ("local_only", "local_only")):
        acc = accepted_view(rows, policy)
        leaks = sum(1 for a in acc if not a["right"])
        # Same decisions as 04_harness: the leak count must match policies.json.
        assert abs(leaks / n - pol[policy]["leak_share"]) < 0.002, (policy, leaks, pol[policy]["leak_share"])
        m = {"policy": policy, "accepted": len(acc), "leaks": leaks, "leaks_by_tier": {},
             "random_audit": random_audit(acc, n)}
        for a in acc:
            if not a["right"]:
                m["leaks_by_tier"][a["tier"]] = m["leaks_by_tier"].get(a["tier"], 0) + 1
        m["misstated_total"] = round(sum(misstated(a, gt_total) for a in acc if not a["right"]), 2)
        m["leaks_under_10_cents"] = sum(1 for a in acc if not a["right"] and 0 < misstated(a, gt_total) < 0.10)
        if mode == "cloud":
            m["amount_recheck_t4"] = amount_recheck(rows, acc, n, gt_total)
        summary["modes"][mode] = m

    out = res / "backstop"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

    pc = lambda v: "n/a" if v is None else f"{v * 100:.0f}%"  # noqa: E731
    L = [f"# Backstops for leaks (auto-accepted but wrong), {args.results}, n = {n}, tau = {TAU}", ""]
    for mode, m in summary["modes"].items():
        L += [f"## {mode} ({m['policy']}): {m['accepted']} auto-accepted, {m['leaks']} leaks {m['leaks_by_tier']}; "
              f"misstated total {m['misstated_total']}, {m['leaks_under_10_cents']} leaks off by under 0.10", "",
              "Random audit of auto-accepted receipts (exact expectation, sampling without replacement)", "",
              "| audit | receipts audited | per 1k | expected leaks caught | share of leaks | P(find >= 1 leak) |", "|---|---|---|---|---|---|"]
        L += [f"| {pc(a['p'])} | {a['audited']} | {a['audited_per_1k']} | {a['expected_leaks_caught']} | {pc(a['share_of_leaks_caught'])} | {pc(a['p_find_at_least_one'])} |"
              for a in m["random_audit"]]
        if "amount_recheck_t4" in m:
            L += ["", "Top X% of auto-accepted receipts by accepted total, re-read by T4; disagreement goes to review", "",
                  "| top X% | re-read | leaks caught | correct sent to review | extra review per 1k | extra USD per 1k | extra images to cloud | misstated amount covered |",
                  "|---|---|---|---|---|---|---|---|"]
            L += [f"| {pc(r['x'])} | {r['rechecked']} | {r['leaks_caught']} of {r['leaks_total']} | {r['false_flags']} | {r['extra_review_per_1k']} | "
                  f"{r['extra_usd_per_1k']:.3f} | {pc(r['extra_cloud_sent_share'])} | {pc(r['misstated_covered_share'])} of {r['misstated_total']} |" for r in m["amount_recheck_t4"]]
        L.append("")
    (out / "summary.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
