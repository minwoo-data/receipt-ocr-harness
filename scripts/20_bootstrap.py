"""20_bootstrap.py - 95% bootstrap intervals for the headline numbers (one run, so the only
uncertainty we can measure is which receipts happened to be in the sample).

Receipts are resampled with replacement (B = 10,000, seed 20261031); every policy is replayed on the
same resample, so differences between policies are paired. Percentile intervals.
Decisions come from the same decide() as 04_harness.py (tau = 0.9) on <results>/harness/per_receipt.jsonl;
the point estimates are asserted equal to policies.json.

    python scripts/20_bootstrap.py --results results
    python scripts/20_bootstrap.py --results results_wild
Output: <results>/harness/bootstrap.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("harness04", ROOT / "scripts" / "04_harness.py")
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)

POLICIES = ("all_lite", "harness", "local_only")
METRICS = ("accepted_money_precision", "review_share", "cloud_sent_share", "cost_usd_per_1k")
PAIRS = (("all_lite", "harness"), ("harness", "local_only"))      # a - b, accuracy points
B, SEED, TAU = 10_000, 20261031, 0.9


def vectors(rows: list[dict], policy: str) -> dict[str, np.ndarray]:
    acc, ok, rev, sent, cost, costed = [], [], [], [], [], []
    for r in rows:
        d = H.decide(r, policy, {"tau": TAU})
        is_acc = d["tier"] != "review"
        acc.append(is_acc)
        ok.append(is_acc and bool(r[d["tier"].lower()]["money_ok"]))
        rev.append(not is_acc)
        sent.append(any(t in ("T3", "T4") for t in d["path"]))
        c = all(r[t.lower()]["available"] for t in d["path"])
        costed.append(c)
        cost.append(d["cost"] if c else 0.0)
    return {k: np.array(v, dtype=float) for k, v in
            (("acc", acc), ("ok", ok), ("rev", rev), ("sent", sent), ("cost", cost), ("costed", costed))}


def metrics(v: dict[str, np.ndarray], idx: np.ndarray) -> dict[str, np.ndarray]:
    """idx: (B, n) resample indices -> one value per resample."""
    a, o = v["acc"][idx].sum(1), v["ok"][idx].sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return {"accepted_money_precision": o / a,
                "review_share": v["rev"][idx].mean(1),
                "cloud_sent_share": v["sent"][idx].mean(1),
                "cost_usd_per_1k": v["cost"][idx].sum(1) / v["costed"][idx].sum(1) * 1000}


def ci(x: np.ndarray) -> list[float]:
    lo, hi = np.nanpercentile(x, [2.5, 97.5])
    return [round(float(lo), 4), round(float(hi), 4)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    args = ap.parse_args()
    res = ROOT / args.results
    rows = [json.loads(l) for l in (res / "harness" / "per_receipt.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    n = len(rows)
    pol = {p["policy"]: p for p in json.loads((res / "harness" / "policies.json").read_text(encoding="utf-8"))}

    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, n, size=(B, n))
    full = np.arange(n)[None, :]
    V = {p: vectors(rows, p) for p in POLICIES}
    boot = {p: metrics(V[p], idx) for p in POLICIES}
    out = {"n": n, "B": B, "seed": SEED, "tau": TAU, "method": "percentile, paired resampling of receipts", "policies": {}, "differences": {}}
    for p in POLICIES:
        point = {k: float(v[0]) for k, v in metrics(V[p], full).items()}
        for k in METRICS:        # same decisions as 04_harness.py
            ref = pol[p][k]
            assert ref is None or abs(point[k] - ref) < (0.002 if k != "cost_usd_per_1k" else 0.002), (p, k, point[k], ref)
        out["policies"][p] = {k: {"point": round(point[k], 4), "ci95": ci(boot[p][k])} for k in METRICS}
    for a, b in PAIRS:
        d = (boot[a]["accepted_money_precision"] - boot[b]["accepted_money_precision"]) * 100
        pt = (out["policies"][a]["accepted_money_precision"]["point"] - out["policies"][b]["accepted_money_precision"]["point"]) * 100
        out["differences"][f"{a}_minus_{b}_points"] = {"point": round(pt, 2), "ci95": [round(float(x), 2) for x in np.nanpercentile(d, [2.5, 97.5])],
                                                       "share_of_resamples_above_0": round(float(np.mean(d > 0)), 4)}
    path = res / "harness" / "bootstrap.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for p, m in out["policies"].items():
        print(p, {k: (v["point"], v["ci95"]) for k, v in m.items()})
    print(out["differences"])
    print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
