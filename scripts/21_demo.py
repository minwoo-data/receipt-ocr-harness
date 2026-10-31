"""21_demo.py - booth demo: one receipt at a time, step by step, in local-only mode. No cloud calls.

Replay (default): cases are picked by code from the cached local reads (RapidOCR, Tesseract,
Qwen2.5-VL 3B) of SROIE 300 and the synthetic set, and every step is recomputed with the same
functions the harness uses (rules.extract, local_signal, verify checks). The decision is asserted
equal to 04_harness.decide(row, "local_only"). Gemini outputs are never read.

Live (optional): --image runs RapidOCR + Tesseract + rules on this machine, then Qwen2.5-VL 3B on a
local Ollama server if one answers on localhost (start it with `CUDA_VISIBLE_DEVICES=-1 ollama serve`),
and adds that receipt as the first case. One heavy process at a time.

Output: demo/index.html (git-ignored: it shows SROIE images, which this repository does not
redistribute). Self-contained, no network. Keys: right arrow or space = next step, left = back,
1-9 = case, A = show all.

    python scripts/21_demo.py
    python scripts/21_demo.py --image path/to/receipt.jpg [--month-first] [--no-vlm]
"""

from __future__ import annotations

import argparse
import html as H
import importlib.util
import json
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from harness import palette as PAL  # noqa: E402
from harness import verify  # noqa: E402
from harness.normalize import norm_date  # noqa: E402
from harness.scoring import predicted_fields  # noqa: E402

_spec = importlib.util.spec_from_file_location("harness04", ROOT / "scripts" / "04_harness.py")
H04 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H04)

OUT = ROOT / "demo" / "index.html"
TAU = 0.9
SYNTH_TODAY = date(2026, 10, 31)          # same window as 08_synth_eval.py
SYNTH_MIN_YEAR = SYNTH_TODAY.year - 2


def jload(p: Path) -> dict | None:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def money(v) -> str | None:
    try:
        return None if v is None else f"{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)


def lines_with(lines: list[str], token: str | None) -> list[int]:
    return [i for i, l in enumerate(lines) if token and token in l.replace(",", "")]


# ---------------------------------------------------------------------------
# Steps, recomputed from cached records with the harness's own functions
# ---------------------------------------------------------------------------
def t1_step(rapid: dict, tess: dict | None, day_first: bool, today: date, min_year: int) -> dict:
    rp = predicted_fields(rapid, day_first=day_first)
    tp = predicted_fields(tess, day_first=day_first) if tess else {"date": None, "total": None}
    sig = H04.local_signal(rapid, tess, day_first)
    date_ok = rp["date"] is not None and not verify.check_date({"date": rp["date"]}, today=today, min_year=min_year)
    lines = rapid.get("lines") or []
    return {"lines": lines, "hl": lines_with(lines, money(rp["total"])), "n_lines": len(lines),
            "latency_s": round((rapid.get("latency_ms") or 0) / 1000, 1), "conf": round(sig["conf"], 3),
            "date": rp["date"], "total": money(rp["total"]), "w_date": tp["date"], "w_total": money(tp["total"]),
            "complete": sig["complete"], "agree": sig["agree"], "conf_ok": sig["conf"] >= TAU, "date_ok": date_ok,
            "same": rp["date"] is not None and rp["total"] is not None and (rp["date"], rp["total"]) == (tp["date"], tp["total"]),
            "sure": bool(sig["agree"] and sig["conf"] >= TAU and date_ok), "reasons": rapid.get("rule_reasons") or []}


def checks_step(rec: dict | None, ocr_lines: list[str] | None, rapid_lines: list[str], today: date, min_year: int):
    """The four checks of the poster, each with what it looked at. Returns (rows, flag names, T2 view)."""
    if rec is None:
        return [], {"UNAVAILABLE"}, None
    data = rec.get("data")
    if not isinstance(data, dict):
        row = {"name": "Sanitizer", "ok": False, "detail": "the model returned no parseable JSON"}
        return [row], {"G_MISSING"}, {"answer": {}, "latency_s": round((rec.get("latency_ms") or 0) / 1000, 1)}
    names: set[str] = set()

    san = verify.check_sanitizer(rec) + verify.check_missing(data) + verify.check_range(data)
    names |= {f.name for f in san}
    rows = [{"name": "Sanitizer", "what": "injection patterns (EN/KO/JA/ZH), field whitelist, type and range",
             "ok": not san, "detail": "; ".join(f"{f.name}: {f.detail}" for f in san) if san else
             "no injection pattern; vendor, date and total present; total in range"}]

    ar = verify.check_arithmetic(data)
    names |= {f.name for f in ar}
    parts = [(k, data.get(k)) for k in ("subtotal", "tax", "tip", "discount") if data.get(k) is not None]
    if data.get("subtotal") is None or data.get("total") is None:
        ar_detail = "abstains: the model read no subtotal, so there is nothing to add up"
    elif ar:
        ar_detail = ar[0].detail
    else:
        ar_detail = " + ".join(f"{k} {money(v)}" for k, v in parts) + f" = total {money(data.get('total'))} (within 0.05)"
    rows.append({"name": "Arithmetic", "what": "subtotal + tax + tip + discount = total", "ok": not ar, "detail": ar_detail})

    dt = verify.check_date(data, today=today, min_year=min_year)
    names |= {f.name for f in dt}
    iso = norm_date(data.get("date"), day_first=True)
    rows.append({"name": "Date plausibility", "what": f"inside the receipts' era, {min_year} to {today.isoformat()}",
                 "ok": not dt, "detail": f"{iso}: {dt[0].detail}" if dt else f"{iso} is inside the window"})

    ag = verify.check_agreement(data, ocr_lines)
    names |= {f.name for f in ag}
    bits = []
    tot = money(data.get("total"))
    if any(f.name == "G_AGREE_TOTAL" for f in ag):
        bits.append(f"total {tot} is not in the OCR text")
    elif tot:
        bits.append(f"total {tot} is in the OCR text")
    cands = verify.ocr_date_candidates(ocr_lines or [])
    if any(f.name == "G_AGREE_DATE" for f in ag):
        bits.append(f"date {iso} differs from the OCR's {', '.join(sorted(cands)[:2])}")
    elif iso and cands:
        bits.append(f"date {iso} matches the OCR")
    elif iso:
        bits.append("date: abstains, the OCR saw no date")
    rows.append({"name": "Two-reader agreement", "what": "the model's total and date must appear in the independent OCR text",
                 "ok": not ag, "detail": "; ".join(bits), "hl": lines_with(rapid_lines, tot)})

    t2 = {"answer": {k: data.get(k) for k in ("vendor", "date", "subtotal", "tax", "total")},
          "conf": data.get("confidence"), "latency_s": round((rec.get("latency_ms") or 0) / 1000, 1)}
    return rows, names, t2


def build_case(cid: str, title: str, shows: str, source: str, image: str | None, rapid: dict, tess: dict | None,
               qwen: dict | None, day_first: bool, today: date, min_year: int, truth: dict | None) -> dict:
    from harness.rules import refresh
    rapid, tess = refresh(rapid, day_first), refresh(tess, day_first)       # same current-rules view as 04_harness
    t1 = t1_step(rapid, tess, day_first, today, min_year)
    ocr_lines = ((rapid or {}).get("lines") or []) + ((tess or {}).get("lines") or [])
    checks, names, t2 = checks_step(qwen, ocr_lines or None, t1["lines"], today, min_year)
    if t1["sure"]:
        decision = {"kind": "t1", "label": "Auto-accept from T1", "why": "both OCR readers agree, confidence is at least 0.9 and the date is plausible"}
        accepted = {"date": t1["date"], "total": t1["total"]}
    elif qwen is not None and not names:
        decision = {"kind": "t2", "label": "Auto-accept from the local VLM", "why": "all four checks passed"}
        accepted = {"date": norm_date((qwen.get("data") or {}).get("date"), day_first=day_first), "total": money((qwen.get("data") or {}).get("total"))}
    else:
        failed = [c["name"] for c in checks if not c["ok"]] or ["no local VLM answer"]
        decision = {"kind": "review", "label": "Human review", "why": "flagged by: " + ", ".join(failed)}
        accepted = None
    if truth is not None:
        tr = {"date": truth.get("date"), "total": money(truth.get("total"))}
        truth = {**tr, "right": None if accepted is None else (accepted["date"] == tr["date"] and accepted["total"] == tr["total"])}
    return {"id": cid, "title": title, "shows": shows, "source": source, "image": image, "t1": t1,
            "t2": t2, "checks": checks, "flag_names": sorted(names), "decision": decision, "accepted": accepted, "truth": truth}


# ---------------------------------------------------------------------------
# Case picking (by code, deterministic: shortest receipts first, then key)
# ---------------------------------------------------------------------------
def sroie_cases() -> list[dict]:
    man = {it["key"]: it for it in map(json.loads, filter(str.strip, (ROOT / "data/manifest/sroie300.jsonl").read_text(encoding="utf-8").splitlines()))}
    rows = [json.loads(l) for l in (ROOT / "results/harness/per_receipt.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    years = sorted(int(it["gt"]["date"][:4]) for it in man.values() if it["gt"].get("date"))
    today, min_year = date(years[-1], 12, 31), years[0]          # same window as 04_harness.py
    rec = lambda eng, k: jload(ROOT / "results" / eng / f"{k}.json")  # noqa: E731
    nlines = lambda r: len((rec("rapidocr", r["key"]) or {}).get("lines") or [])  # noqa: E731

    def first(pred):
        c = sorted((r for r in rows if pred(r, H04.decide(r, "local_only", {"tau": TAU}))), key=lambda r: (nlines(r), r["key"]))
        return c[0] if c else None

    picks = [
        ("sure", "T1 is sure", "Two OCR readers agree, so the cheapest reader's answer is accepted. No model runs.",
         lambda r, d: d["tier"] == "T1" and r["t1"]["money_ok"]),
        ("pass", "Local VLM passes every check", "T1 is unsure; the local VLM reads it and all four checks pass.",
         lambda r, d: d["tier"] == "T2" and r["t2"]["money_ok"] and (rec("qwen", r["key"]) or {}).get("data", {}).get("subtotal") is not None
         and verify.ocr_date_candidates(((rec("rapidocr", r["key"]) or {}).get("lines") or []) + ((rec("tesseract", r["key"]) or {}).get("lines") or []))),
        ("arith", "Arithmetic catches a misread", "The local VLM's numbers do not add up, so a person checks it.",
         lambda r, d: d["tier"] == "review" and not r["t2"]["money_ok"] and "G_ARITH" in r["flags"]["t2"]),
        ("agree", "Two readers disagree", "The model's total is not a number the OCR engine saw anywhere on the receipt.",
         lambda r, d: d["tier"] == "review" and not r["t2"]["money_ok"] and "G_AGREE_TOTAL" in r["flags"]["t2"] and "G_ARITH" not in r["flags"]["t2"]),
        ("leak", "A miss: wrong, yet every check passes", "Checks are not an answer key. This wrong answer is auto-accepted (a leak).",
         lambda r, d: d["tier"] == "T2" and not r["t2"]["money_ok"]),
    ]
    out = []
    for cid, title, shows, pred in picks:
        r = first(pred)
        if r is None:
            print("no receipt for case", cid)
            continue
        k, it = r["key"], man[r["key"]]
        case = build_case(cid, title, shows, f"SROIE {k} (CC-BY-4.0), run of 2026-10-31", "../" + it["image"],
                          rec("rapidocr", k), rec("tesseract", k), rec("qwen", k), True, today, min_year, it["gt"])
        # Same flags and the same decision as the harness.
        assert set(case["flag_names"]) == set(r["flags"]["t2"]), (k, case["flag_names"], r["flags"]["t2"])
        d = H04.decide(r, "local_only", {"tau": TAU})["tier"]
        assert {"t1": "T1", "t2": "T2", "review": "review"}[case["decision"]["kind"]] == d, (k, d)
        out.append(case)
    return out


def synth_cases() -> list[dict]:
    items = list(map(json.loads, filter(str.strip, (ROOT / "data/synthetic/manifest.jsonl").read_text(encoding="utf-8").splitlines())))
    rec = lambda eng, k: jload(ROOT / "results" / "synth" / eng / f"{k}.json")  # noqa: E731
    picks = [
        ("inject", "Prompt injection on the receipt", "Text printed on the receipt tries to instruct the model; the sanitizer flags the answer.",
         lambda it, c: it["category"].startswith("inject") and not c["t1"]["sure"] and "G_SANITIZER" in c["flag_names"]),
        ("datetrap", "Date trap: both OCR readers agree", "A receipt dated two years ahead. The OCR readers agree, "
         "but T1's date fails the plausibility check, so the local VLM reads it and the checks send it to a person.",
         lambda it, c: it["category"] == "date_blatant" and c["t1"]["agree"] and c["t1"]["conf_ok"] and not c["t1"]["date_ok"]),
    ]
    out = []
    for cid, title, shows, pred in picks:
        for it in items:
            k = it["key"]
            c = build_case(cid, title, shows, f"synthetic {k} ({it['category']}, {it.get('variant')})", "../" + it["image"],
                           rec("rapidocr", k), rec("tesseract", k), rec("qwen", k), True, SYNTH_TODAY, SYNTH_MIN_YEAR, it["gt"])
            if pred(it, c):
                if cid == "datetrap":
                    c["truth"]["after"] = ("Before the fix of 2026-10-31, T1 being sure was enough and this receipt was "
                                           "auto-accepted with a future date.")
                out.append(c)
                break
    return out


def live_case(image: Path, month_first: bool, use_vlm: bool) -> dict:
    from harness import rules
    from harness.engines import traditional
    dest = OUT.parent / "live" / image.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(image, dest)
    day_first = not month_first
    recs = {}
    for eng in ("rapidocr", "tesseract"):                      # one heavy process at a time
        out = traditional.ENGINES[eng](dest)
        rr = rules.extract(out["lines"], day_first=day_first)
        out["fields"], out["rule_reasons"], out["total_candidates"] = {"company": rr.company, "date": rr.date, "total": rr.total}, rr.reasons, rr.total_candidates
        recs[eng] = out
    qwen = None
    if use_vlm:
        import requests
        from harness.engines import vlm
        try:
            requests.get("http://localhost:11434/api/tags", timeout=2).raise_for_status()
            print("Ollama is up: running Qwen2.5-VL 3B (about 30 s)")
            qwen = vlm.run_ollama(dest)
        except requests.RequestException:
            print("no Ollama server on localhost: the live case stops after T1")
    today = date.today()
    return build_case("live", "Your receipt, read on this laptop", "Read just now: RapidOCR, Tesseract and Qwen2.5-VL 3B, all local.",
                      f"live: {image.name}", "live/" + image.name, recs["rapidocr"], recs["tesseract"], qwen, day_first,
                      today, today.year - 3, None)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
CSS = f"""
:root {{ --bg:#ffffff; --fg:{PAL.INK}; --fg2:{PAL.INK2}; --rule:{PAL.GRID}; --t1:{PAL.TIER['T1']}; --t2:{PAL.TIER['T2']};
  --t1tint:{PAL.TIER_TINT['T1']}; --t2tint:{PAL.TIER_TINT['T2']}; --rev:{PAL.TIER['review']}; --revtint:{PAL.TIER_TINT['review']};
  --good:{PAL.GOOD}; --flag:#b42318; --flagtint:#fdecea; --accent:{PAL.ACCENT_TEXT}; --card:#ffffff; --panel:#f5f7fa; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#111418; --fg:#e8eaee; --fg2:#a2abb6; --rule:#2c3138; --t1tint:#16263a;
  --t2tint:#1a2533; --revtint:#1c1e21; --flag:#f97066; --flagtint:#2d1715; --accent:#9db7dc; --card:#1a1e24; --panel:#161c24; --good:#8cc79a; color-scheme:dark; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font-family:Arial, Helvetica, sans-serif; font-size:18px; line-height:1.45; }}
header {{ padding:14px 20px 10px; border-bottom:1px solid var(--rule); display:grid; gap:10px; }}
.top {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:8px 18px; }}
h1 {{ font-size:28px; margin:0; letter-spacing:-0.01em; }}
.badge {{ font-size:14px; font-weight:bold; color:var(--t1); border:2px solid var(--t1); padding:3px 9px; border-radius:999px; }}
.tabs {{ display:flex; flex-wrap:wrap; gap:6px; }}
.tabs button {{ font:inherit; font-size:15px; padding:6px 11px; border:1.5px solid var(--rule); background:var(--card); color:var(--fg); border-radius:6px; cursor:pointer; }}
.tabs button[aria-pressed=true] {{ border-color:var(--fg); font-weight:bold; }}
.tabs button span {{ color:var(--fg2); margin-right:5px; }}
main {{ display:grid; gap:18px; padding:16px 20px 90px; }}
@media (min-width:1000px) {{ main {{ grid-template-columns:minmax(300px, 0.8fr) 1.4fr; align-items:start; }} .imgcol {{ position:sticky; top:12px; }} }}
.imgcol {{ background:var(--panel); border:1px solid var(--rule); padding:10px; display:grid; gap:6px; }}
.imgcol img {{ width:100%; max-height:78vh; object-fit:contain; background:#fff; cursor:zoom-in; }}
.imgcol img.zoom {{ max-height:none; cursor:zoom-out; }}
.src {{ font-size:13px; color:var(--fg2); }}
.shows {{ font-size:19px; margin:0 0 4px; }}
.shows b {{ display:block; font-size:24px; margin-bottom:2px; }}
.step {{ border:1px solid var(--rule); border-left:6px solid var(--rule); background:var(--card); padding:12px 14px; margin-top:12px; transition:opacity .2s; }}
.step.pending {{ opacity:0.28; }}
.step.pending .body {{ visibility:hidden; height:0; overflow:hidden; }}
.step h2 {{ font-size:20px; margin:0 0 8px; display:flex; gap:10px; align-items:center; }}
.num {{ width:28px; height:28px; border-radius:50%; background:var(--fg); color:var(--bg); font-size:15px; display:inline-flex; align-items:center; justify-content:center; flex:none; }}
.step.t1 {{ border-left-color:var(--t1); }} .step.t2 {{ border-left-color:var(--t2); }}
.step.dec.t1, .step.dec.t2 {{ background:var(--t1tint); }} .step.dec.review {{ border-left-color:var(--rev); background:var(--revtint); }}
.ocr {{ font-family:Consolas, "Courier New", monospace; font-size:14px; background:var(--panel); border:1px solid var(--rule); max-height:230px; overflow:auto; padding:6px 8px; white-space:pre; margin:6px 0 10px; }}
.ocr .hl {{ background:#ffe58a; color:#111; }}
table.kv {{ border-collapse:collapse; font-variant-numeric:tabular-nums; margin:4px 0 8px; }}
table.kv th, table.kv td {{ text-align:left; padding:4px 14px 4px 0; border-bottom:1px solid var(--rule); }}
table.kv th {{ font-size:13px; color:var(--fg2); font-weight:normal; text-transform:uppercase; letter-spacing:0.05em; }}
.chips {{ display:flex; flex-wrap:wrap; gap:6px; margin:6px 0; }}
.chip {{ font-size:15px; border:1.5px solid var(--rule); padding:3px 9px; border-radius:999px; }}
.chip.ok {{ border-color:var(--good); }} .chip.no {{ border-color:var(--flag); }}
.verdict {{ font-weight:bold; font-size:19px; margin-top:6px; }}
.check {{ display:grid; grid-template-columns:34px 1fr; gap:2px 8px; padding:8px 0; border-bottom:1px solid var(--rule); }}
.check .mk {{ grid-row:span 2; font-size:22px; font-weight:bold; line-height:1; padding-top:2px; }}
.check.ok .mk {{ color:var(--good); }} .check.no {{ background:var(--flagtint); }} .check.no .mk {{ color:var(--flag); }}
.check .what {{ color:var(--fg2); font-size:15px; }}
.check .detail {{ grid-column:2; font-size:16px; }}
.muted {{ color:var(--fg2); }}
.big {{ font-size:28px; font-weight:bold; }}
.note {{ font-size:15px; color:var(--fg2); margin-top:6px; }}
.right {{ color:var(--good); font-weight:bold; }} .wrong {{ color:var(--flag); font-weight:bold; }}
.bar {{ position:fixed; left:0; right:0; bottom:0; background:var(--bg); border-top:1px solid var(--rule); padding:10px 20px; display:flex; gap:8px; flex-wrap:wrap; align-items:center; }}
.bar button {{ font:inherit; font-size:17px; padding:9px 16px; border-radius:6px; border:1.5px solid var(--fg); background:var(--card); color:var(--fg); cursor:pointer; }}
.bar button.primary {{ background:var(--t1); border-color:var(--t1); color:#fff; font-weight:bold; }}
.bar .hint {{ font-size:13px; color:var(--fg2); margin-left:auto; }}
button:focus-visible {{ outline:3px solid var(--accent); outline-offset:2px; }}
"""

JS = r"""
const CASES = JSON.parse(document.getElementById('cases').textContent);
let ci = 0, shown = 1;
const $ = (s) => document.querySelector(s);
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined && text !== null) e.textContent = text; return e; }
function val(v) { return (v === null || v === undefined || v === '') ? '—' : String(v); }
function chip(ok, text) { return el('span', 'chip ' + (ok ? 'ok' : 'no'), (ok ? '✓ ' : '✗ ') + text); }
function step(n, cls, title, body) {
  const s = el('section', 'step ' + cls); const h = el('h2'); h.append(el('span', 'num', n), el('span', '', title)); s.append(h);
  const b = el('div', 'body'); body(b); s.append(b); return s;
}
function ocrBox(lines, hl) {
  const box = el('div', 'ocr'); const set = new Set(hl || []);
  lines.forEach((l, i) => { const d = el('div', set.has(i) ? 'hl' : '', l || ' '); box.append(d); });
  return box;
}
function render() {
  const c = CASES[ci];
  document.querySelectorAll('.tabs button').forEach((b, i) => b.setAttribute('aria-pressed', i === ci));
  const img = $('#img'); if (c.image) { img.src = c.image; img.alt = 'Receipt image: ' + c.source; img.hidden = false; } else { img.hidden = true; }
  $('#src').textContent = c.source;
  const steps = $('#steps'); steps.replaceChildren();
  const sh = el('p', 'shows'); sh.append(el('b', '', c.title), document.createTextNode(c.shows)); steps.append(sh);
  const t1 = c.t1;
  steps.append(step(1, 't1', 'T1 · local OCR + rules (RapidOCR, Tesseract as witness)', (b) => {
    b.append(el('div', 'muted', `RapidOCR read ${t1.n_lines} lines in ${t1.latency_s} s · mean confidence ${t1.conf}. Highlighted: the line with T1's total.`));
    b.append(ocrBox(t1.lines, t1.hl));
    const t = el('table', 'kv'); const hr = el('tr'); ['', 'RapidOCR + rules', 'Tesseract (witness)'].forEach(x => hr.append(el('th', '', x))); t.append(hr);
    [['date', t1.date, t1.w_date], ['total', t1.total, t1.w_total]].forEach(([k, a, w]) => { const r = el('tr'); r.append(el('td', '', k), el('td', '', val(a)), el('td', '', val(w))); t.append(r); });
    b.append(t);
    const ch = el('div', 'chips');
    ch.append(chip(t1.complete, t1.complete ? 'rules found date and total, no warning' : 'rules warned: ' + (t1.reasons.join(', ') || 'a field is missing')),
              chip(t1.same, 'both readers give the same date and total'), chip(t1.conf_ok, 'confidence ≥ 0.9'),
              chip(t1.date_ok, t1.date_ok ? 'date is plausible' : 'date is not plausible'));
    b.append(ch);
    b.append(el('div', 'verdict', t1.sure ? 'T1 is sure → accept, nothing else runs' : 'T1 is not sure → ask the local VLM'));
  }));
  steps.append(step(2, 't2', 'T2 · local VLM (Qwen2.5-VL 3B on a 4 GB laptop GPU)', (b) => {
    if (t1.sure) { b.append(el('div', 'muted', 'Skipped: T1 was sure.')); return; }
    if (!c.t2) { b.append(el('div', 'muted', 'No local VLM answer (Ollama not running).')); return; }
    const a = c.t2.answer || {}; const t = el('table', 'kv');
    ['vendor', 'date', 'subtotal', 'tax', 'total'].forEach(k => { const r = el('tr'); r.append(el('th', '', k), el('td', '', val(a[k]))); t.append(r); });
    b.append(t);
    b.append(el('div', 'note', `Answered in ${c.t2.latency_s} s${c.id === 'live' ? '' : ' (replayed from the run of 2026-10-31)'}. The model's own confidence (${val(c.t2.conf)}) is logged and never used to approve.`));
  }));
  steps.append(step(3, 't2', 'Four code checks, no answer key', (b) => {
    if (t1.sure) {
      b.append(el('div', 'muted', 'Not run: the checks read model answers, and T1 was accepted on the two-reader agreement and its date check.'));
      return;
    }
    c.checks.forEach(k => {
      const r = el('div', 'check ' + (k.ok ? 'ok' : 'no')); r.append(el('span', 'mk', k.ok ? '✓' : '✗'));
      const head = el('div'); head.append(el('b', '', k.name + ' '), el('span', 'what', k.what || '')); r.append(head, el('div', 'detail', k.detail));
      b.append(r);
    });
  }));
  const d = c.decision;
  steps.append(step(4, 'dec ' + d.kind, 'Decision', (b) => { b.append(el('div', 'big', d.label), el('div', 'muted', d.why)); }));
  steps.append(step(5, '', 'Answer key (shown only for the demo)', (b) => {
    if (!c.truth) { b.append(el('div', 'muted', 'No answer key for a live receipt: you are the answer key.')); return; }
    b.append(el('div', '', `Ground truth: date ${val(c.truth.date)}, total ${val(c.truth.total)}`));
    if (c.truth.right === null) b.append(el('div', 'muted', 'A person keys it in, so it ends up right at the cost of their time.'));
    else b.append(el('div', c.truth.right ? 'right' : 'wrong', c.truth.right ? '✓ The accepted answer is right.' : '✗ The accepted answer is wrong: a leak.'));
    if (c.truth.after) b.append(el('div', 'note', c.truth.after));
  }));
  paint();
}
function paint() {
  document.querySelectorAll('#steps .step').forEach((s, i) => s.classList.toggle('pending', i >= shown));
  $('#next').disabled = shown >= 5;
}
function go(i) { ci = (i + CASES.length) % CASES.length; shown = 1; render(); window.scrollTo(0, 0); }
const tabs = $('.tabs');
CASES.forEach((c, i) => { const b = el('button'); b.type = 'button'; b.append(el('span', '', String(i + 1)), document.createTextNode(c.title)); b.onclick = () => go(i); tabs.append(b); });
$('#next').onclick = () => { if (shown < 5) { shown++; paint(); const s = document.querySelectorAll('#steps .step')[shown - 1]; if (s) s.scrollIntoView({behavior: 'smooth', block: 'nearest'}); } };
$('#back').onclick = () => { if (shown > 1) { shown--; paint(); } };
$('#all').onclick = () => { shown = 5; paint(); };
$('#nextcase').onclick = () => go(ci + 1);
$('#img').onclick = (e) => e.target.classList.toggle('zoom');
document.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); $('#next').click(); }
  else if (e.key === 'ArrowLeft') $('#back').click();
  else if (e.key === 'a' || e.key === 'A') $('#all').click();
  else if (/^[1-9]$/.test(e.key) && +e.key <= CASES.length) go(+e.key - 1);
});
render();
"""


def page(cases: list[dict]) -> str:
    data = json.dumps(cases, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Local-only demo</title><style>{CSS}</style></head>
<body>
<header>
  <div class="top"><h1>One receipt, local-only mode</h1><span class="badge">0 cloud calls · everything on this laptop</span></div>
  <div class="tabs" role="group" aria-label="Cases"></div>
</header>
<main>
  <div class="imgcol"><img id="img" alt=""><div class="src" id="src"></div></div>
  <div id="steps" aria-live="polite"></div>
</main>
<div class="bar">
  <button type="button" id="back">◀ Back</button>
  <button type="button" class="primary" id="next">Next step ▶</button>
  <button type="button" id="all">Show all</button>
  <button type="button" id="nextcase">Next case</button>
  <span class="hint">→ / space next · ← back · A all · 1–{len(cases)} case · click the image to zoom</span>
</div>
<script type="application/json" id="cases">{data}</script>
<script>{JS}</script>
</body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", type=Path, help="a receipt image to read live on this machine")
    ap.add_argument("--month-first", action="store_true", help="the live receipt prints dates month-first (US)")
    ap.add_argument("--no-vlm", action="store_true", help="live mode: stop after T1, do not call Ollama")
    args = ap.parse_args()
    cases = sroie_cases() + synth_cases()
    if args.image:
        cases.insert(0, live_case(args.image.resolve(), args.month_first, not args.no_vlm))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page(cases), encoding="utf-8")
    for c in cases:
        print(f"{c['id']:7} {c['source']:<60} -> {c['decision']['label']}" + ("" if not c["truth"] else f" | right={c['truth']['right']}"))
    print("wrote", OUT.relative_to(ROOT), "(git-ignored, open it in a browser)")


if __name__ == "__main__":
    main()
