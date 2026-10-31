"""10_fill_poster.py - Inject result numbers into poster/poster.html.

Reads:
    results/scores/summary.json          (03_score)
    results/harness/policies.json        (04_harness)
    results/synth/eval_<engine>.json     (08_synth_eval)
    results/retry/<engine>_summary.json  (05_retry)
Writes:
    poster/poster.html   (placeholders such as [T1]% replaced in place)
    poster/numbers.json  (every number used, for the README and the pitch)

Run after every data refresh; it is idempotent because it also reads the
untouched template poster/poster.template.html when present (created on first run).
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTER = ROOT / "poster" / "poster.html"
TEMPLATE = ROOT / "poster" / "poster.template.html"


def jload(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def pct(v) -> str:
    return "n/a" if v is None else f"{v*100:.1f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cloud", default="gemini-lite", help="engine used for the adversarial and retry tables")
    args = ap.parse_args()

    if not TEMPLATE.exists():
        shutil.copy(POSTER, TEMPLATE)
    html = TEMPLATE.read_text(encoding="utf-8")
    numbers: dict = {}

    # {{key}} placeholders: one number source shared with the workflow and landing pages.
    import re
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from harness.report_numbers import numbers as report_numbers
    V = report_numbers()
    numbers["report"] = V
    def _fill(m):
        assert m.group(1) in V, f"poster placeholder {{{{{m.group(1)}}}}} has no value in report_numbers"
        return str(V[m.group(1)])
    html = re.sub(r"\{\{(\w+)\}\}", _fill, html)

    scores = {s["engine"]: s for s in (jload(ROOT / "results" / "scores" / "summary.json") or [])}
    tier_map = {"T1": "rapidocr", "T2": "qwen", "T3": "gemini-lite", "T4": "gemini"}
    for tier, eng in tier_map.items():
        s = scores.get(eng)
        if not s:
            continue
        money = None
        # date+total both right is not in summary.json; derive from the per-receipt file
        rows_path = ROOT / "results" / "scores" / f"{eng}.jsonl"
        if rows_path.exists():
            rows = [json.loads(l) for l in rows_path.open(encoding="utf-8") if l.strip()]
            ok = [r for r in rows if r["correct"]["date"] is not None and r["correct"]["total"] is not None]
            money = sum(1 for r in ok if r["correct"]["date"] and r["correct"]["total"]) / len(ok) if ok else None
        numbers[tier] = {"engine": eng, "n": s["n"], "date_total": money, "latency_ms_median": s["latency_ms_median"],
                         "usd_per_1k": s["cost_usd_per_1k"], "company": s["acc"]["company"], "date": s["acc"]["date"], "total": s["acc"]["total"]}
        html = html.replace(f"[{tier}]%", f"{pct(money)}%")
        html = html.replace(f"[{tier}ms] s", f"{(s['latency_ms_median'] or 0)/1000:.1f} s")
        html = html.replace(f"[{tier}usd]", f"{s['cost_usd_per_1k']:.2f}" if s["cost_usd_per_1k"] else "0")

    policies = {p["policy"]: p for p in (jload(ROOT / "results" / "harness" / "policies.json") or [])}
    numbers["policies"] = policies
    # Routing table: sent to cloud | review | accepted right | USD / 1k, every cell from JSON.
    def cells(sent, review, prec, usd):
        usd_txt = "0" if not usd else f"{usd:.2f}"
        return "".join(f'<td class="num">{v}</td>' for v in (f"{sent*100:.0f}%", f"{review*100:.0f}%", f"{prec*100:.1f}%", usd_txt))
    for name in ("oracle", "router", "harness", "local_only"):
        p = policies.get(name)
        if p:
            html = html.replace(f"[pol:{name}]", cells(p["cloud_sent_share"], p["review_share"], p["accepted_money_precision"], p["cost_usd_per_1k"]))
    lr = jload(ROOT / "results" / "learned_router" / "curve.json")
    if lr:
        hd = lr["headline"]; numbers["learned"] = hd
        html = html.replace("[pol:learned]", cells(hd["share_at_router_share"], 0.0, hd["precision_at_router_share"], hd["cost_at_router_share"]))
        html = html.replace("[lr:auc]", f"{hd['auc']:.2f}")

    synth = jload(ROOT / "results" / "synth" / f"eval_{args.cloud}.json")
    if synth:
        cats = synth["by_category"]
        groups = {"Date traps": ["date_blatant", "date_subtle"], "Arithmetic traps": ["amount_blatant", "amount_subtle"],
                  "Injection, blatant": ["inject_blatant"], "Injection, disguised": ["inject_subtle"], "Controls": ["control"]}
        numbers["synth"] = {}
        for label, keys in groups.items():
            agg = {"n": 0, "fooled": 0, "expected_fired": 0, "leaked": 0}
            for k in keys:
                c = cats.get(k)
                if c:
                    for f in agg:
                        agg[f] += c[f]
            numbers["synth"][label] = agg
            row_old = f"<tr><td>{label}</td><td class=\"num\">[n]</td><td class=\"num\">[f]</td><td class=\"num\">[c]</td><td class=\"num\">[l]</td></tr>"
            row_new = (f"<tr><td>{label}</td><td class=\"num\">{agg['n']}</td><td class=\"num\">{agg['fooled']}</td>"
                       f"<td class=\"num\">{agg['expected_fired']}</td><td class=\"num\">{agg['leaked']}</td></tr>")
            html = html.replace(row_old, row_new)

    retry = jload(ROOT / "results" / "retry" / f"{args.cloud}_summary.json")
    if retry:
        s = retry["summary"]
        numbers["retry"] = s
        for mode, tags in (("blind", ("b1", "b2", "b3")), ("guided", ("g1", "g2", "g3"))):
            m = s.get(mode) or {}
            html = html.replace(f"[{tags[0]}]", str(m.get("fixed", "n/a")))
            html = html.replace(f"[{tags[1]}]", str(m.get("broke", "n/a")))
            html = html.replace(f"[{tags[2]}]", f"{m.get('kept_ok', 'n/a')} / {m.get('n', 'n/a')}")
        html = html.replace("Targeted retry on flagged receipts", f"Targeted retry on {s.get('n_flagged', '?')} flagged receipts")

    findings = jload(ROOT / "poster" / "findings.json")
    if findings:
        for i, text in enumerate(findings.get("bullets", []), start=1):
            marker_start = f"[finding {i}:"
            a = html.find(marker_start)
            if a != -1:
                b = html.find("]", a)
                html = html[:a] + text + html[b + 1:]

    POSTER.write_text(html, encoding="utf-8")
    (ROOT / "poster" / "numbers.json").write_text(json.dumps(numbers, indent=1, ensure_ascii=False), encoding="utf-8")
    left = [tok for tok in ("[T1]", "[T2]", "[T3]", "[T4]", "[n]", "[b1]", "[g1]", "[finding", "[pol:", "[lr:") if tok in html]
    print("placeholders still unfilled:", left or "none")


if __name__ == "__main__":
    main()
