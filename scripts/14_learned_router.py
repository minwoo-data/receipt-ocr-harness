"""14_learned_router.py - Learned escalation signal (plan §A).

    python scripts/14_learned_router.py --results results                      # 5-fold out-of-fold on SROIE
    python scripts/14_learned_router.py --results results_wild --fit-from results   # transfer check
Outputs: <results>/learned_router/{model.json, curve.json, summary.md}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from harness.features import FEATURE_NAMES, SCHEMA_VERSION, features  # noqa: E402


def load(root: Path):
    schema = json.loads((root / "harness" / "per_receipt.schema.json").read_text(encoding="utf-8"))
    assert schema["schema_version"] == 1
    rows = [json.loads(l) for l in (root / "harness" / "per_receipt.jsonl").open(encoding="utf-8") if l.strip()]
    X, y, t3ok, t3cost, keys = [], [], [], [], []
    for r in rows:
        if r["t1"]["money_ok"] is None or r["t3"]["money_ok"] is None:
            continue
        rapid = json.loads((root / "rapidocr" / f"{r['key']}.json").read_text(encoding="utf-8")) if (root / "rapidocr" / f"{r['key']}.json").exists() else None
        tf = root / "tesseract" / f"{r['key']}.json"
        tess = json.loads(tf.read_text(encoding="utf-8")) if tf.exists() else None
        X.append([features(rapid, tess, r["signal"])[k] for k in FEATURE_NAMES])
        y.append(0 if r["t1"]["money_ok"] else 1)          # 1 = tier 1 wrong -> should escalate
        t3ok.append(bool(r["t3"]["money_ok"]))
        t3cost.append(float(r["t3"].get("cost") or 0.0))
        keys.append(r["key"])
    return np.array(X), np.array(y), np.array(t3ok), np.array(t3cost), keys


def curve(scores, y, t3ok, t3cost):
    """Replay rule: score >= thr -> T3 recorded correctness (blind); else T1. Every distinct score is a threshold.
    No review step, so the share sent to the cloud equals the share answered by the cloud."""
    pts = []
    t1ok = (y == 0)
    for thr in sorted(set(scores.tolist()) | {float("inf")}):
        esc = scores >= thr
        ok = np.where(esc, t3ok, t1ok)
        pts.append({"threshold": None if thr == float("inf") else float(thr), "cloud_share": float(esc.mean()),
                    "accepted_precision": float(ok.mean()), "cost_usd_per_1k": round(float((esc * t3cost).mean()) * 1000, 3)})
    return pts


def headline(pts, router):
    share, prec = router["cloud_sent_share"], router["accepted_money_precision"]
    at_share = max((p for p in pts if p["cloud_share"] <= share), key=lambda p: p["cloud_share"], default=None)
    reach = min((p["cloud_share"] for p in pts if p["accepted_precision"] >= prec), default=None)
    return {"router_cloud_share": share, "router_precision": prec,
            "precision_at_router_share": at_share["accepted_precision"] if at_share else None,
            "share_at_router_share": at_share["cloud_share"] if at_share else None,
            "cost_at_router_share": at_share["cost_usd_per_1k"] if at_share else None,
            "cloud_share_at_router_precision": reach if reach is not None else "not reached",
            "win_precision": bool(at_share and at_share["accepted_precision"] > prec),
            "win_share": bool(reach is not None and reach < share)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--fit-from", default=None, help="fit on this root and score --results (transfer)")
    args = ap.parse_args()
    root = ROOT / args.results
    X, y, t3ok, t3cost, keys = load(root)
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    if args.fit_from:
        Xf, yf, _, _, _ = load(ROOT / args.fit_from)
        model.fit(Xf, yf)
        scores = model.predict_proba(X)[:, 1]
        mode = f"fit on {args.fit_from}, scored on {args.results}"
    else:
        scores = np.zeros(len(y))
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=20261031).split(X, y):
            m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(X[tr], y[tr])
            scores[te] = m.predict_proba(X[te])[:, 1]
        model.fit(X, y)
        mode = "5-fold out-of-fold"
    pts = curve(scores, y, t3ok, t3cost)
    policies = {p["policy"]: p for p in json.loads((root / "harness" / "policies.json").read_text(encoding="utf-8"))}
    head = headline(pts, policies["router"])
    head["oracle_cloud_share"], head["oracle_precision"] = policies["oracle"]["cloud_sent_share"], policies["oracle"]["accepted_money_precision"]
    head["auc"] = float(roc_auc_score(y, scores)) if len(set(y.tolist())) > 1 else None
    head["n"], head["mode"] = int(len(y)), mode
    out = root / "learned_router"
    out.mkdir(exist_ok=True)
    lr = model.named_steps["logisticregression"]
    (out / "model.json").write_text(json.dumps({"schema_version": SCHEMA_VERSION, "feature_names": FEATURE_NAMES,
                                                "coef": lr.coef_[0].tolist(), "intercept": float(lr.intercept_[0]),
                                                "source_fields": "harness.features.ALLOWED_SOURCE_KEYS", "mode": mode}, indent=1), encoding="utf-8")
    (out / "curve.json").write_text(json.dumps({"headline": head, "points": pts}, indent=1), encoding="utf-8")
    md = [f"# Learned escalation signal ({args.results}; {mode}; n={head['n']})", "",
          f"- AUC (tier-1 wrong vs right): {head['auc']:.3f}" if head["auc"] is not None else "- AUC: n/a",
          f"- rule router: cloud share {head['router_cloud_share']:.1%}, precision {head['router_precision']:.1%}",
          f"- learned, precision at the router's cloud share: {head['precision_at_router_share']:.1%}" if head["precision_at_router_share"] is not None else "- precision at router share: n/a",
          f"- learned, cloud share needed for the router's precision: {head['cloud_share_at_router_precision'] if isinstance(head['cloud_share_at_router_precision'], str) else format(head['cloud_share_at_router_precision'], '.1%')}",
          f"- oracle: cloud share {head['oracle_cloud_share']:.1%}, precision {head['oracle_precision']:.1%}",
          f"- verdict: {'WIN' if head['win_precision'] and head['win_share'] else 'PARTIAL' if head['win_precision'] or head['win_share'] else 'NO GAIN'}",
          "", "| coefficient | feature |", "|---|---|"]
    for c, f in sorted(zip(lr.coef_[0].tolist(), FEATURE_NAMES), key=lambda t: -abs(t[0])):
        md.append(f"| {c:+.2f} | {f} |")
    (out / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:8]))


if __name__ == "__main__":
    main()
