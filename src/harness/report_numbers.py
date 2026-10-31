"""report_numbers.py - every number that the poster, the workflow pages and the
QR landing page print, computed in one place from the results JSON.

    from harness.report_numbers import numbers
    V = numbers()          # dict of display strings, e.g. V["precA"] == "96.9%"

Sources: results/harness/policies.json (SROIE 300), results_wild/harness/policies.json
(WildReceipt 200), results/harness/waterfall.json, results/learned_router/curve.json,
results/synth/eval_gemini-lite.json, results*/gate_total_label/comparison.json,
results*/harness/bootstrap.json (20_bootstrap), results*/backstop/summary.json (19_backstop).

People's time is an assumption, not a measurement: REVIEW_MINUTES per reviewed receipt at
REVIEW_WAGE_USD_H, overridable with the environment variables HARNESS_REVIEW_MINUTES and
HARNESS_REVIEW_WAGE_USD_H. API cost is measured (token counts x 2026-10-31 prices).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REVIEW_MINUTES = float(os.environ.get("HARNESS_REVIEW_MINUTES", "1"))        # a person keys date + total from the image
REVIEW_WAGE_USD_H = float(os.environ.get("HARNESS_REVIEW_WAGE_USD_H", "20"))  # loaded hourly cost of that person

# README routing table, in print order: (policy in policies.json, label)
ROUTING_ROWS = (
    ("all_local", "All local (tier 1)"),
    ("all_lite", "All cloud, cheap"),
    ("all_strong", "All cloud, strong"),
    ("oracle", "Oracle router (escalates exactly the local misses)"),
    ("router", "Router: both OCR readers agree and confidence >= 0.9, else cloud"),
    ("harness", "Harness: router + code checks, flagged answers escalate, then review"),
    ("harness_ladder", "Harness with local VLM rung"),
    ("local_only", "Local only: T1, then local VLM with code checks, else review (no cloud)"),
)
EN_DASH, MINUS = "–", "−"


def _j(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def pct(x: float, nd: int = 1) -> str:
    """Percent with half-up rounding on the decimal value (0.865 -> 87%, not the float artefact 86%)."""
    from decimal import ROUND_HALF_UP, Decimal
    q = Decimal(1).scaleb(-nd) if nd else Decimal(1)
    return f"{Decimal(str(round(x * 100, 6))).quantize(q, rounding=ROUND_HALF_UP)}%"


def pct_t(x: float) -> str:
    """Table percent: exact 0 and 1 print as 0% and 100%, everything else with one decimal."""
    return "0%" if x == 0 else "100%" if x == 1 else pct(x)


def span(lo: float, hi: float, nd: int = 1) -> str:
    """95% interval of a share: '94.7-98.6%' with an en dash."""
    return f"{pct(lo, nd).rstrip('%')}{EN_DASH}{pct(hi, nd)}"


def pts(lo: float, hi: float) -> str:
    """Interval of a difference in points: '-1.9 to +2.9' with a true minus sign."""
    sg = lambda v: f"{'+' if v > 0 else MINUS if v < 0 else ''}{abs(v):.1f}"  # noqa: E731
    return f"{sg(lo)} to {sg(hi)}"


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
    V.update(_after_poster(P, PW))
    return V


def _after_poster(P: dict, PW: dict) -> dict:
    """Numbers added after the poster was printed: people's time, 95% intervals, backstops."""
    X: dict = {}
    # 1. people's time, added to the measured API cost
    per_review = REVIEW_MINUTES / 60 * REVIEW_WAGE_USD_H
    people = lambda p: p["review_share"] * 1000 * per_review  # noqa: E731
    total = lambda p: p["cost_usd_per_1k"] + people(p)  # noqa: E731
    X.update(review_min=f"{REVIEW_MINUTES:g}", review_wage=f"{REVIEW_WAGE_USD_H:g}", review_usd=f"{per_review:.2f}")
    X["routing_rows"] = [{
        "policy": k, "label": label, "accept": pct_t(P[k]["auto_accept_share"]), "review": pct_t(P[k]["review_share"]),
        "sent": pct(P[k]["cloud_sent_share"], 0), "prec": pct(P[k]["accepted_money_precision"]),
        "leaks_1k": f"{P[k]['leak_share'] * 1000:.0f}", "api": f"{P[k]['cost_usd_per_1k']:.2f}",
        "people": f"{people(P[k]):.2f}", "total": f"{total(P[k]):.2f}"} for k, label in ROUTING_ROWS]
    h, lite, lo = P["harness"], P["all_lite"], P["local_only"]
    X.update(totA=f"{total(h):.2f}", totT3=f"{total(lite):.2f}", totB=f"{total(lo):.2f}",
             peopleA=f"{people(h):.2f}", peopleB=f"{people(lo):.2f}",
             wtotA=f"{total(PW['harness']):.2f}", wtotT3=f"{total(PW['all_lite']):.2f}", wtotB=f"{total(PW['local_only']):.2f}")
    saved = lite["cost_usd_per_1k"] - h["cost_usd_per_1k"]           # API dollars the harness saves per 1k
    X["api_saved"] = f"{saved:.2f}"
    be = saved / (h["review_share"] * 1000)                          # a review must cost less than this to break even
    X.update(breakeven_usd=f"{be:.3f}", breakeven_s=f"{be / REVIEW_WAGE_USD_H * 3600:.1f}")
    X["tot_ratio"] = f"{float(X['totA']) / float(X['totT3']):.0f}"

    # 2. 95% bootstrap intervals (paired resampling of receipts)
    for tag, rel in (("", "results"), ("w", "results_wild")):
        B = _j(f"{rel}/harness/bootstrap.json")
        bp, bd = B["policies"], B["differences"]
        X[f"{tag}ciA"] = span(*bp["harness"]["accepted_money_precision"]["ci95"])
        X[f"{tag}ciB"] = span(*bp["local_only"]["accepted_money_precision"]["ci95"])
        X[f"{tag}ciT3"] = span(*bp["all_lite"]["accepted_money_precision"]["ci95"])
        X[f"{tag}ci_revA"] = span(*bp["harness"]["review_share"]["ci95"])
        X[f"{tag}ci_revB"] = span(*bp["local_only"]["review_share"]["ci95"])
        X[f"{tag}ci_sentA"] = span(*bp["harness"]["cloud_sent_share"]["ci95"], 0)
        c = bp["harness"]["cost_usd_per_1k"]["ci95"]
        X[f"{tag}ci_costA"] = f"{c[0]:.2f}{EN_DASH}{c[1]:.2f}"
        gA, gB = bd["all_lite_minus_harness_points"], bd["harness_minus_local_only_points"]
        # point gaps from the printed (rounded) values, as everywhere else; intervals from the resamples
        r1 = lambda pol: float(pct(bp[pol]["accepted_money_precision"]["point"]).rstrip("%"))  # noqa: E731
        sg = lambda v: f"{'+' if v > 0 else MINUS if v < 0 else ''}{abs(v):.1f}"  # noqa: E731
        X[f"{tag}gapA"], X[f"{tag}gapA_ci"] = sg(r1("all_lite") - r1("harness")), pts(*gA["ci95"])
        X[f"{tag}gapB"], X[f"{tag}gapB_ci"] = sg(r1("harness") - r1("local_only")), pts(*gB["ci95"])
        X[f"{tag}gapA_zero"] = gA["ci95"][0] < 0 < gA["ci95"][1]
        X[f"{tag}gapB_zero"] = gB["ci95"][0] < 0 < gB["ci95"][1]
        X[f"{tag}boot_B"] = f"{B['B']:,}"

    # 3. backstops for leaks (auto-accepted but wrong), cloud mode
    for tag, rel in (("", "results"), ("w", "results_wild")):
        S = _j(f"{rel}/backstop/summary.json")
        n, cm, lm = S["n"], S["modes"]["cloud"], S["modes"]["local_only"]
        X[f"{tag}bs_leaksA"], X[f"{tag}bs_leaksB"] = cm["leaks"], lm["leaks"]
        X[f"{tag}bs_leaksA_T1"] = cm["leaks_by_tier"].get("T1", 0)
        X[f"{tag}bs_small"] = cm["leaks_under_10_cents"]
        X[f"{tag}bs_misstated"] = f"{cm['misstated_total']:.2f}"
        X[f"{tag}bs_audit"] = [{"p": pct(a["p"], 0), "per_1k": f"{a['audited_per_1k']:.0f}",
                                "caught_1k": f"{a['expected_leaks_caught'] / n * 1000:.1f}",
                                "share": pct(a["share_of_leaks_caught"], 0), "p_find": pct(a["p_find_at_least_one"], 0),
                                "people_1k": f"{a['audited_per_1k'] * per_review:.2f}"}
                               for a in cm["random_audit"]]
        X[f"{tag}bs_recheck"] = [{"x": pct(r["x"], 0), "reread": r["rechecked"], "caught": r["leaks_caught"], "of": r["leaks_total"],
                                  "false": r["false_flags"], "usd_1k": f"{r['extra_usd_per_1k']:.2f}",
                                  "people_1k": f"{r['extra_review_per_1k'] * per_review:.2f}",
                                  "sent": pct(r["extra_cloud_sent_share"], 0),
                                  "misstated": "n/a" if r["misstated_covered_share"] is None else pct(r["misstated_covered_share"], 0)}
                                 for r in cm["amount_recheck_t4"]]

    # 4. the correction of 2026-10-31: what moved since the printed poster
    fixes = [json.loads(l) for l in (ROOT / "data/manifest/wild200_gt_corrections.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    X["wild_fixed_values"], X["wild_fixed_receipts"] = len(fixes), len({f["key"] for f in fixes})

    # 5. README tables that used to be typed by hand (they move when the data is corrected)
    WF = {w["tier"]: w for w in _j("results/harness/waterfall.json")}
    WFW = {w["tier"]: w for w in _j("results_wild/harness/waterfall.json")}
    X["waterfall_rows"] = [{"reader": name, "errors": w["model_errors"], "caught": w["errors_caught"],
                            "pct": pct(w["errors_caught"] / w["model_errors"], 0) if w["model_errors"] else "n/a",
                            "leaked": w["errors_leaked"], "false": w["false_flags"]}
                           for name, w in (("Local VLM (SROIE)", WF["t2"]), ("Flash-Lite (SROIE)", WF["t3"]),
                                           ("3.6 Flash (SROIE)", WF["t4"]), ("Local VLM (Wild photos)", WFW["t2"]),
                                           ("Flash-Lite (Wild photos)", WFW["t3"]))]
    X["lr_rows"] = []
    for name, rel in (("SROIE 300 (out of fold)", "results"), ("Wild 200 (transfer)", "results_wild")):
        L = _j(f"{rel}/learned_router/curve.json")["headline"]
        win_p, win_s = L["precision_at_router_share"] > L["router_precision"], L["cloud_share_at_router_precision"] < L["router_cloud_share"]
        X["lr_rows"].append({"set": name, "auc": f"{L['auc']:.3f}", "router": f"{pct(L['router_cloud_share'], 0)} cloud, {pct(L['router_precision'])}",
                             "learned": pct(L["precision_at_router_share"]), "share": pct(L["cloud_share_at_router_precision"], 0),
                             "verdict": "gain" if win_p and win_s else "partial: fewer cloud calls, same precision" if win_s else
                             "partial: higher precision" if win_p else "no gain"})
    X["leak_classes"] = {}
    for tag, rel in (("", "results"), ("w", "results_wild")):
        rows = [json.loads(l) for l in (ROOT / rel / "leaks" / "leaks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        by: dict = {}
        for r in rows:
            by[r["class"]] = by.get(r["class"], 0) + 1
        X["leak_classes"][tag or "s"] = {"n": len(rows), **by}
        X[f"{tag}leak_n"] = len(rows)
        X[f"{tag}leak_other_printed"] = by.get("total_other_printed_amount", 0)
        X[f"{tag}leak_dates"] = by.get("date_other", 0) + by.get("date_day_month_swapped", 0)
        X[f"{tag}leak_swapped"] = by.get("date_day_month_swapped", 0)
        X[f"{tag}leak_both"] = by.get("both_wrong", 0)
    X["gate_rows"] = []
    for name, rel in (("SROIE 300 (dev, gate designed here)", "results"), ("Wild 200 (held-out)", "results_wild")):
        G = _j(f"{rel}/gate_total_label/comparison.json")
        rec = lambda right: len({x["key"] for x in G["changed_verdicts"] if x["answer_right"] == right})  # noqa: E731
        ba = lambda pol, m: f"{pct(G['policies'][pol][m]['before'])} -> {pct(G['policies'][pol][m]['after'])}"  # noqa: E731
        X["gate_rows"].append({"set": name, "caught": f"{G['caught_leaks']} ({rec(False)})", "false": f"{G['new_false_flags']} ({rec(True)})",
                               "hA": ba("harness", "accepted_money_precision"), "hA_rev": ba("harness", "review_share"),
                               "lo": ba("local_only", "accepted_money_precision"), "lo_rev": ba("local_only", "review_share")})
    return X


# Numbers the poster printed that a later fix can move, with a label for the correction table.
CORRECTABLE = (
    ("aT1", "T1 alone (RapidOCR + rules), scans"),
    ("t1", "Harness: accepted at T1, never left the machine, scans"),
    ("sent", "Harness: sent to the cloud, scans"),
    ("costA", "Harness: USD per 1,000, scans"),
    ("cost_cut", "Harness: cost below all-cloud, scans"),
    ("oracle_cloud", "Oracle router: sent to the cloud, scans"),
    ("router_cloud", "Router: sent to the cloud, scans"),
    ("precB", "Local only: accepted answers correct, scans"),
    ("revB", "Local only: sent to people, scans"),
    ("scan_gap", "Local only below the harness, scans (points)"),
    ("wT1", "T1 alone, photos"),
    ("wT2", "Local VLM alone, photos"),
    ("wT3", "Flash-Lite alone, photos"),
    ("wT4", "3.6 Flash alone, photos"),
    ("wA", "Harness: accepted answers correct, photos"),
    ("wArev", "Harness: sent to people, photos"),
    ("wB", "Local only: accepted answers correct, photos"),
    ("wBrev", "Local only: sent to people, photos"),
    ("auc", "Learned hand-off score, AUC (scans, out of fold)"),
    ("lr_prec", "Learned score at the router's cloud share, scans"),
)


def corrections(V: dict | None = None) -> list[dict]:
    """Rows {label, printed, now} for every CORRECTABLE number that differs from poster/printed_numbers.json."""
    V = V or numbers()
    printed = _j("poster/printed_numbers.json")["numbers"]
    return [{"key": k, "label": label, "printed": printed[k], "now": V[k]} for k, label in CORRECTABLE if str(printed[k]) != str(V[k])]
