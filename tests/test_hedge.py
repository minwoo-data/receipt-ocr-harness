import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("harness04", ROOT / "scripts" / "04_harness.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def ev(ok=True, latency_ms=1000, cost=0.0, available=True):
    return {"pred": {}, "correct": {}, "money_ok": ok, "all_ok": ok, "cost": cost, "latency_ms": latency_ms, "available": available}


def row(t2_lat=30000, t2_flags=(), t3_flags=(), t2_ok=True, t3_ok=True):
    return {"key": "k", "t1": ev(), "t1b": ev(), "t2": ev(t2_ok, t2_lat), "t3": ev(t3_ok, 1800, 0.0005), "t4": ev(),
            "signal": {"agree": True, "conf": 1.0, "complete": True},
            "flags": {"t2": list(t2_flags), "t3": list(t3_flags), "t4": []}}


def test_d_zero_fires_cloud_for_every_receipt():
    d = h.decide(row(), "hedge", {"D": 0.0, "scale": 1.0})
    assert d["cloud_fired"] is True and "T3" in d["path"]
    # cloud arrives at 1.8 s, local at 30 s: cloud answer accepted first
    assert d["tier"] == "T3" and d["latency_kind"] == "wall"


def test_d_infinity_never_fires_cloud_and_flagged_local_goes_to_review():
    d = h.decide(row(t2_flags=["G_ARITH"]), "hedge", {"D": h.INF, "scale": 1.0})
    assert d["cloud_fired"] is False and d["path"] == ["T2"] and d["tier"] == "review"


def test_fast_local_wins_when_under_budget_and_scale_applies():
    d = h.decide(row(t2_lat=16000), "hedge", {"D": 5.0, "scale": 0.25})   # 16 s * 0.25 = 4 s <= D
    assert d["cloud_fired"] is False and d["tier"] == "T2" and d["latency_ms"] == 4000


def test_both_flagged_is_review_and_cost_counts_every_fired_call():
    d = h.decide(row(t2_flags=["G_ARITH"], t3_flags=["G_AGREE_TOTAL"]), "hedge", {"D": 5.0, "scale": 1.0})
    assert d["tier"] == "review" and d["cloud_fired"] is True and abs(d["cost"] - 0.0005) < 1e-9
