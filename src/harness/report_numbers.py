"""report_numbers.py - every number that the poster, the workflow pages and the
QR landing page print, computed in one place from the results JSON.

    from harness.report_numbers import numbers
    V = numbers()          # dict of display strings, e.g. V["precA"] == "96.9%"

Sources: results/harness/policies.json (SROIE 300), results_wild/harness/policies.json
(WildReceipt 200), results/harness/waterfall.json, results/learned_router/curve.json,
results/synth/eval_gemini-lite.json, results*/gate_total_label/comparison.json.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _j(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def pct(x: float, nd: int = 1) -> str:
    """Percent with half-up rounding on the decimal value (0.865 -> 87%, not the float artefact 86%)."""
    from decimal import ROUND_HALF_UP, Decimal
    q = Decimal(1).scaleb(-nd) if nd else Decimal(1)
    return f"{Decimal(str(round(x * 100, 6))).quantize(q, rounding=ROUND_HALF_UP)}%"


def secs(ms: float) -> str:
    return f"{ms / 1000:.1f}" if ms < 10000 else f"{ms / 1000:.0f}"


def numbers() -> dict:
    P = {p["policy"]: p for p in _j("results/harness/policies.json")}
    PW = {p["policy"]: p for p in _j("results_wild/harness/policies.json")}
    W = {w["tier"]: w for w in _j("results/harness/waterfall.json")}
    LR = _j("results/learned_router/curve.json")["headline"]
    SY = _j("results/synth/eval_gemini-lite.json")["by_category"]
    G = _j("results/gate_total_label/comparison.json")
    GW = _j("results_wild/gate_total_label/comparison.json")
    from harness.features import FEATURE_NAMES

    h, lo = P["harness"], P["local_only"]
    n = h["n"]
    t1 = h["tier_share"]["T1"]
    sent = h["cloud_sent_share"]
    t3acc, t4acc, revA = h["tier_share"]["T3"], h["tier_share"]["T4"], h["review_share"]
    t2acc, revB = lo["tier_share"]["T2"], lo["review_share"]
    assert abs(sent - (1 - t1)) < 0.002 and abs(sent - (t3acc + t4acc + revA)) < 0.002, "harness shares do not add up"
    assert abs((1 - t1) - (t2acc + revB)) < 0.002 and lo["cloud_sent_share"] == 0, "local-only shares do not add up"

    V: dict = {"n": n, "n_wild": PW["harness"]["n"]}
    alone = {"T1": "all_local", "T2": "all_qwen", "T3": "all_lite", "T4": "all_strong"}
    for k, pol in alone.items():
        a, aw = P[pol], PW[pol]
        V[f"a{k}"] = pct(a["accepted_money_precision"])            # scans, one decimal
        V[f"a{k}i"] = pct(a["accepted_money_precision"], 0)        # scans, whole percent
        V[f"w{k}"] = pct(aw["accepted_money_precision"])           # photos
        V[f"w{k}i"] = pct(aw["accepted_money_precision"], 0)
        V[f"s{k}"] = secs(a["latency_ms_median"])
        V[f"ms{k}"] = f"{a['latency_ms_median'] / 1000:.1f}"
        V[f"c{k}"] = f"{a['cost_usd_per_1k']:.2f}"
    V.update(
        t1=pct(t1), sent=pct(sent), senti=pct(sent, 0), t3=pct(t3acc), t4=pct(t4acc), toT4=pct(t4acc + revA), revA=pct(revA),
        t2=pct(t2acc), revB=pct(revB), revBi=pct(revB, 0),
        accA=pct(h["auto_accept_share"]), accB=pct(lo["auto_accept_share"]),
        nrevA=round(revA * n), nrevB=round(revB * n),
        precA=pct(h["accepted_money_precision"]), precB=pct(lo["accepted_money_precision"]),
        costA=f"{h['cost_usd_per_1k']:.2f}", latA=secs(h["latency_ms_median"]), latB=secs(lo["latency_ms_median"]),
        oracle_cloud=pct(P["oracle"]["cloud_sent_share"]), oracle_cloudi=pct(P["oracle"]["cloud_sent_share"], 0),
        oracle_prec=pct(P["oracle"]["accepted_money_precision"]),
        router_cloud=pct(P["router"]["cloud_sent_share"]), router_cloudi=pct(P["router"]["cloud_sent_share"], 0),
        router_prec=pct(P["router"]["accepted_money_precision"]),
        wA=pct(PW["harness"]["accepted_money_precision"]), wArev=pct(PW["harness"]["review_share"]),
        wB=pct(PW["local_only"]["accepted_money_precision"]), wBrev=pct(PW["local_only"]["review_share"]),
        c2=W["t2"]["errors_caught"], e2=W["t2"]["model_errors"], c3=W["t3"]["errors_caught"], e3=W["t3"]["model_errors"],
        c4=W["t4"]["errors_caught"], e4=W["t4"]["model_errors"],
        auc=f"{LR['auc']:.2f}", n_features=len(FEATURE_NAMES), lr_share=pct(LR["share_at_router_share"], 0),
        lr_prec=pct(LR["precision_at_router_share"]),
    )
    # Differences and ratios are computed from the printed (rounded) values, so a reader's own arithmetic matches.
    f = lambda key: float(V[key].rstrip("%"))
    V["scan_gap"] = f"{f('precA') - f('precB'):.1f}"
    V["cloud_gap"] = f"{f('aT3') - f('precA'):.1f}"
    V["cost_cut"] = pct(1 - float(V["costA"]) / float(V["cT3"]), 0)
    V["t1i"] = pct(t1, 0)
    V["leakA"], V["leakB"] = round(h["leak_share"] * n), round(lo["leak_share"] * n)
    # strong vs cheap cloud tier: accuracy gain in points and price ratio, from the printed values
    V["strong_gain"] = f"{f('aT4') - f('aT3'):.1f}"
    V["strong_ratio"] = f"{float(V['cT4']) / float(V['cT3']):.1f}"
    # adversarial set (cloud, cheap)
    cat = lambda *ks: {f: sum(SY[k][f] for k in ks) for f in ("n", "fooled", "expected_fired", "leaked")}
    inj, trap = cat("inject_blatant", "inject_subtle"), cat("date_blatant", "date_subtle", "amount_blatant", "amount_subtle")
    V.update(synth_n=sum(c["n"] for c in SY.values()), inj_n=inj["n"], inj_fooled=inj["fooled"], trap_n=trap["n"],
             trap_fired=trap["expected_fired"], synth_leaked=sum(c["leaked"] for c in SY.values()))
    # gate experiment D
    rec = lambda c, right: len({x["key"] for x in c["changed_verdicts"] if x["answer_right"] == right})
    V.update(d_caught=G["caught_leaks"], d_false=G["new_false_flags"], d_wild_caught_rcpt=rec(GW, False), d_wild_false_rcpt=rec(GW, True))
    V["leak_other"] = sum(1 for l in (ROOT / "results/leaks/leaks.jsonl").read_text(encoding="utf-8").splitlines()
                          if l.strip() and json.loads(l)["class"] == "total_other_printed_amount")
    return V
