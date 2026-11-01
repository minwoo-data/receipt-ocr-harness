"""18_landing.py - docs/index.html, the page behind the poster's "How it works & code" QR.

Phone first (people scan the QR): the architecture is drawn as stacked HTML boxes that sit side by
side on wide screens, then the three questions with the poster's numbers and figures, then links.
Served by GitHub Pages from /docs, so the figures are copied into docs/assets/.
Numbers: src/harness/report_numbers.py (same source as the poster). Colors: src/harness/palette.py.
    python scripts/18_landing.py
"""
import html as H
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from harness import palette as PAL  # noqa: E402
from harness.report_numbers import corrections, numbers  # noqa: E402

V = numbers()
CORR = corrections(V)
REPO = "https://github.com/minwoo-data/receipt-ocr-harness"
ASSETS = ROOT / "docs" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)
for f in ("fig_outcomes.png", "fig_sweep.png"):
    shutil.copyfile(ROOT / "results" / "figures" / f, ASSETS / f)
shutil.copyfile(ROOT / "poster" / "Park_Minwoo_MISM_ReceiptOCR.pdf", ASSETS / "Park_Minwoo_MISM_ReceiptOCR.pdf")

e = lambda s: H.escape(str(s))
T = PAL.TIER

def node(cls, title, lines, step=None, step_cls=""):
    st = f'<span class="step {step_cls}">{e(step)}</span>' if step else ""
    body = "".join(f"<span>{e(l)}</span>" for l in lines)
    return f'<div class="node {cls}{"" if step else " nostep"}">{st}<b>{e(title)}</b>{body}</div>'

arch = f"""
<div class="arch">
  <div class="zone local">
    <div class="zl">On this machine · receipts and checks stay here</div>
    {node("in", "Receipt image", ["file check, resized for the readers"], 1)}
    {node("t1", "T1 · Local OCR + rules", ["RapidOCR + Tesseract witness", f"alone {V['aT1']} · {V['sT1']} s · $0"], 2)}
    {node("har", "Harness: router + code checks", ["sanitizer · arithmetic · date · two-reader", "model self-confidence never approves"], 3)}
    {node("t2", "T2 · Local VLM", ["Qwen2.5-VL 3B on a 4 GB GPU", f"alone {V['aT2']} · {V['sT2']} s · $0", "local-only mode uses this instead of the cloud"], "B", "b")}
    <div class="outs">
      {node("acc", "Auto-accept", [f"cloud mode {V['accA']} · local only {V['accB']}"])}
      {node("rev", "Human review", [f"cloud mode {V['revA']} · local only {V['revB']}"], 6)}
    </div>
  </div>
  <div class="zone cloud">
    <div class="zl">Google Gemini API · cloud</div>
    <p class="leave">{e(V['sent'])} of images leave the machine, at step 4 only</p>
    {node("t3", "T3 · Cloud, cheap", ["Gemini 3.1 Flash-Lite", f"alone {V['aT3']} · {V['sT3']} s · ${V['cT3']}/1k"], 4)}
    {node("t4", "T4 · Cloud, strong", ["Gemini 3.6 Flash, thinking off", f"alone {V['aT4']} · {V['sT4']} s · ${V['cT4']}/1k"], 5)}
    <div class="zone fb">
      <div class="zl">Anthropic API · fallback only</div>
      {node("cl", "Claude Haiku", ["on Gemini 429 / 503 after one fast-fail attempt", "production design; no key in this run"])}
    </div>
  </div>
</div>"""

steps = [
    ("1", "Receipt image arrives", "file check, resized (1,600 px for the cloud, 1,024 px for the local VLM)"),
    ("2", "T1 reads every receipt, locally", "RapidOCR text, Tesseract as a second witness, rules pull vendor / date / total"),
    ("3", f"T1 sure → auto-accept · {V['t1']}", "both OCR readers agree on date and total AND OCR confidence ≥ 0.9"),
    ("4", f"Not sure → T3 Gemini Flash-Lite · {V['sent']}", f"the image leaves the machine only for the cloud readers (steps 4 and 5); checks pass → auto-accept ({V['t3']})"),
    ("5", f"Checks flag T3 → T4 Gemini Flash · {V['toT4']}", f"zero flags → auto-accept ({V['t4']})"),
    ("6", f"Still flagged → human review · {V['revA']}", f"{V['nrevA']} of {V['n']} receipts"),
    ("B", f"Local only: step 4 goes to T2 Qwen2.5-VL · {V['sent']}", f"zero flags → auto-accept ({V['t2']}); flagged → human review ({V['revB']})"),
]
steps_html = "".join(f'<li><span class="sn{" b" if n == "B" else ""}">{e(n)}</span><span class="sm">{e(m)}</span><span class="sa">{e(a)}</span></li>' for n, m, a in steps)

CSS = f"""
:root {{ --bg:#ffffff; --fg:{PAL.INK}; --fg2:{PAL.INK2}; --rule:{PAL.GRID}; --accent:{PAL.ACCENT}; --t1:{T['T1']}; --t2:{T['T2']}; --t3:{T['T3']}; --t4:{T['T4']}; --rev:{T['review']};
  --zone-local:#f5f7fa; --zone-cloud:#fdf4ee; --zone-fb:#f6f6f7; --card:#ffffff; --good:{PAL.GOOD}; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#111418; --fg:#e8eaee; --fg2:#a2abb6; --rule:#2c3138; --accent:#9db7dc; --t1:#9db7dc; --zone-local:#161c24; --zone-cloud:#1f1719; --zone-fb:#18191b; --card:#1a1e24; --good:#8cc79a; color-scheme:dark; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font-family:Arial, Helvetica, sans-serif; font-size:16px; line-height:1.5; }}
.wrap {{ max-width:1080px; margin:0 auto; padding-left:max(16px, env(safe-area-inset-left, 0px)); padding-right:max(16px, env(safe-area-inset-right, 0px)); padding-block:24px 48px; }}
h1 {{ font-size:clamp(32px, 7vw, 52px); line-height:1.05; margin:0; letter-spacing:-0.02em; }}
h1 span {{ color:var(--accent); }}
.lead {{ font-size:clamp(17px, 2.6vw, 20px); margin:10px 0 6px; }}
.who {{ color:var(--fg2); font-size:14px; margin:0; }}
.links {{ display:flex; flex-wrap:wrap; gap:8px; margin:16px 0 4px; }}
.links a {{ display:inline-block; border:1.5px solid var(--fg); color:var(--fg); text-decoration:none; padding:7px 12px; font-size:14px; font-weight:bold; }}
.links a.primary {{ background:var(--accent); border-color:var(--accent); color:var(--bg); }}
nav.qs {{ display:grid; gap:6px; margin:22px 0 0; padding:0; list-style:none; counter-reset:q; }}
nav.qs a {{ color:var(--fg); text-decoration:none; font-weight:bold; font-size:17px; }}
nav.qs a span {{ color:var(--accent); margin-right:6px; }}
h2 {{ font-size:clamp(22px, 4vw, 28px); line-height:1.15; margin:44px 0 6px; padding-top:10px; border-top:2px solid var(--fg); }}
h2 .n {{ color:var(--accent); margin-right:8px; }}
.ans {{ font-size:19px; font-weight:bold; color:var(--accent); margin:0 0 14px; }}
.lbl {{ font-size:12px; letter-spacing:0.08em; text-transform:uppercase; color:var(--fg2); margin:18px 0 6px; }}
p {{ margin:0 0 10px; max-width:68ch; }}
.arch {{ display:grid; gap:12px; margin-top:12px; }}
@media (min-width:860px) {{ .arch {{ grid-template-columns:1.25fr 1fr; align-items:start; }} }}
.zone {{ border:1.5px solid var(--fg2); padding:12px; display:grid; gap:8px; }}
.zone.local {{ background:var(--zone-local); }}
.zone.cloud {{ background:var(--zone-cloud); border-color:var(--t3); border-style:dashed; }}
.zone.fb {{ background:var(--zone-fb); border-style:dashed; margin-top:4px; }}
.zl {{ font-size:12.5px; font-weight:bold; letter-spacing:0.04em; text-transform:uppercase; }}
.leave {{ font-size:14px; font-weight:bold; color:{PAL.CLOUD_TEXT}; margin:0; }}
@media (prefers-color-scheme: dark) {{ .leave {{ color:#f5ad83; }} }}
.node {{ position:relative; background:var(--card); border:1px solid var(--rule); border-top:5px solid var(--fg2); padding:8px 10px 8px 40px; display:grid; gap:1px; font-size:14px; }}
.node b {{ font-size:15.5px; }}
.node span {{ color:var(--fg2); }}
.node.t1 {{ border-top-color:var(--t1); }} .node.t2 {{ border-top-color:var(--t2); }} .node.t3 {{ border-top-color:var(--t3); }} .node.t4 {{ border-top-color:var(--t4); }}
.node.har {{ border:2px solid var(--fg); border-top-width:5px; }}
.node.acc {{ border-top-color:var(--good); }} .node.rev {{ border-top-color:var(--rev); }}
.node.in, .node.cl {{ border-top-color:var(--fg2); }}
.outs {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; }}
@media (max-width:480px) {{ .outs {{ grid-template-columns:1fr; }} }}
.node.nostep {{ padding-left:10px; }}
.step {{ position:absolute; left:9px; top:9px; width:22px; height:22px; border-radius:50%; background:var(--fg); color:var(--bg); font-size:12px; font-weight:bold; display:flex; align-items:center; justify-content:center; }}
.step.b {{ background:var(--t2); color:#111418; }}
ol.steps {{ list-style:none; margin:14px 0 0; padding:0; display:grid; gap:0; }}
ol.steps li {{ display:grid; grid-template-columns:30px minmax(0,1fr); gap:0 8px; padding:8px 0; border-bottom:1px solid var(--rule); }}
.sn {{ grid-row:span 2; width:24px; height:24px; border-radius:50%; background:var(--fg); color:var(--bg); font-weight:bold; font-size:13px; display:flex; align-items:center; justify-content:center; }}
.sn.b {{ background:var(--t2); color:#111418; }}
.sm {{ font-weight:bold; }} .sa {{ color:var(--fg2); font-size:14.5px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:12px; margin:6px 0 12px; }}
.stat .v {{ font-size:34px; font-weight:bold; color:var(--accent); line-height:1; font-variant-numeric:tabular-nums; }}
.stat .c {{ font-size:14px; color:var(--fg2); margin-top:4px; }}
.checks {{ display:grid; gap:6px; margin:0 0 12px; }}
.checks div {{ border-left:3px solid var(--accent); padding-left:10px; }}
figure {{ margin:12px 0; }}
figure .img {{ background:#fff; padding:8px; border:1px solid var(--rule); overflow-x:auto; }}
figure img {{ display:block; width:100%; max-width:820px; height:auto; margin:0 auto; }}
figcaption {{ font-size:14px; color:var(--fg2); margin-top:6px; }}
.cmp {{ width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; margin:6px 0 14px; }}
.cmp th, .cmp td {{ text-align:left; padding:8px 6px; border-bottom:1px solid var(--rule); vertical-align:top; }}
.cmp th {{ font-size:12px; letter-spacing:0.06em; text-transform:uppercase; color:var(--fg2); font-weight:normal; }}
.cmp td b {{ font-size:20px; }} .cmp td span {{ display:block; color:var(--fg2); font-size:14px; }}
.tablewrap {{ overflow-x:auto; }}
.notice {{ border-left:4px solid var(--t3); padding:6px 10px; margin:14px 0 0; font-size:15px; background:var(--zone-cloud); max-width:68ch; }}
.notice a {{ color:var(--fg); font-weight:bold; }}
h3 {{ font-size:18px; margin:22px 0 6px; }}
.cmp.small td, .cmp.small th {{ padding:6px 6px; font-size:15px; }}
details {{ margin:8px 0 12px; }} summary {{ cursor:pointer; font-weight:bold; }}
footer {{ margin-top:44px; padding-top:12px; border-top:1px solid var(--rule); font-size:13px; color:var(--fg2); display:grid; gap:8px; }}
footer a, p a {{ color:var(--accent); }}
a:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}
"""

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>LLM reads, code verifies</title>
<meta name="description" content="A routing and verification harness for receipt OCR: local readers first, cloud models when code checks fail, people last. Minwoo Park, Carnegie Mellon University.">
<style>{CSS}</style></head>
<body><div class="wrap">
<header>
  <h1>LLM reads, <span>code verifies</span></h1>
  <p class="lead">A routing and verification harness for receipt OCR: local readers first, cloud models when code checks fail, people last.</p>
  <p class="who"><b>Minwoo Park</b> · MISM, Business Intelligence &amp; Data Analytics (AI Management) · Carnegie Mellon University · <b>Seeking a Summer 2027 ML/AI engineering internship</b></p>
  <div class="links">
    <a class="primary" href="{REPO}">Code on GitHub</a>
    <a href="{REPO}#readme">Full results</a>
    <a href="assets/Park_Minwoo_MISM_ReceiptOCR.pdf">Poster (PDF)</a>
    <a href="https://minwoopark.dev">Portfolio &amp; resume</a>
  </div>
  <nav class="qs" aria-label="Three questions">
    <a href="#trust"><span>1</span>Can you trust what an LLM reads?</a>
    <a href="#cloud"><span>2</span>When should it call the cloud?</a>
    <a href="#local"><span>3</span>What if the data can't leave?</a>
    <a href="#after"><span>+</span>After the poster: error bars, people's time, misses</a>
  </nav>
  {f'<p class="notice">Numbers on this page were corrected after the poster was printed (a date and amount parsing fix, mostly on the phone photos). <a href="#correction">What changed</a></p>' if CORR else ''}
</header>

<h2 id="how">How it works</h2>
<p>Every receipt starts on the local machine. The harness decides each step with code; a model's own confidence never approves an answer. Numbered steps follow one receipt.</p>
{arch}
<ol class="steps">{steps_html}</ol>

<h2 id="trust"><span class="n">1</span>Can you trust what an LLM reads?</h2>
<p class="ans">Not its confidence. Check every answer with code.</p>
<div class="lbl">Four checks on every model answer</div>
<div class="checks">
  <div><b>Sanitizer:</b> injection patterns in EN/KO/JA/ZH, field whitelist</div>
  <div><b>Arithmetic:</b> subtotal + tax + tip + discount = total</div>
  <div><b>Date plausibility</b></div>
  <div><b>Two-reader agreement:</b> the total and date must appear in the OCR text</div>
</div>
<div class="lbl">With no answer key, the checks caught</div>
<div class="stats">
  <div class="stat"><div class="v">{V['c2']} of {V['e2']}</div><div class="c">wrong answers from the local VLM (scans)</div></div>
  <div class="stat"><div class="v">{V['c3']} of {V['e3']}</div><div class="c">wrong answers from Flash-Lite (scans)</div></div>
</div>
<p>{V['synth_n']} adversarial receipts: {V['inj_n']} prompt injections, {V['inj_fooled']} fooled; {V['trap_n']} date and arithmetic traps, all caught; {V['synth_leaked']} leaked.</p>

<h2 id="cloud"><span class="n">2</span>When should it call the cloud?</h2>
<p class="ans">Local first, cloud when the checks fail, people last.</p>
<figure><div class="img"><a href="assets/fig_outcomes.png" aria-label="Open the full-size chart"><img src="assets/fig_outcomes.png" alt="Stacked bars: where {V['n']} scanned receipts end up under each routing policy, with accepted-answer accuracy and cost per 1,000"></a></div>
<figcaption>Tap a chart to open it full size. Where {V['n']} scans end up under each policy, accepted-answer accuracy and USD per 1,000.</figcaption></figure>
<p><b>Harness (router + 4 checks): within {V['cloud_gap']} points of all-cloud at {V['cost_cut']} lower cost, and {V['t1i']} of receipts never leave the machine.</b> <b>{V['precA']} correct</b> with {V['senti']} of receipts sent to the cloud and {V['revA']} to people, ${V['costA']} per 1,000 (all cloud: {V['aT3']}, ${V['cT3']}). At 2026-10 prices the strong model adds {V['strong_gain']} points for {V['strong_ratio']}× the price: <b>escalate to people, not to a bigger model.</b></p>
<figure><div class="img"><a href="assets/fig_sweep.png" aria-label="Open the full-size chart"><img src="assets/fig_sweep.png" alt="Escalation curve: share of receipts sent to the cloud against accepted-answer accuracy, with the oracle router marked"></a></div>
<figcaption>Share of receipts sent to the cloud vs accuracy as the hand-off threshold moves; ★ = a router that knew the answers.</figcaption></figure>
<p>A router that knew the answers would send only {V['oracle_cloudi']} to the cloud for {V['oracle_prec']}; the router (agree + confidence rule, no checks) sends {V['router_cloudi']} for {V['router_prec']}. <b>The hard part is knowing when to call the cloud, not the model.</b> A learned &ldquo;call the cloud?&rdquo; score (logistic regression, {V['n_features']} features, out-of-fold AUC {V['auc']}) was no better than the router at the same cloud share, so the rule stayed.</p>

<h2 id="local"><span class="n">3</span>What if the data can't leave?</h2>
<p class="ans">Run local-only: same checks, more human review.</p>
<div class="tablewrap"><table class="cmp">
  <tr><th></th><th>Cloud harness</th><th>Local only</th></tr>
  <tr><td>Scans</td><td><b>{V['precA']}</b><span>{V['revA']} to people · ${V['costA']}/1k</span></td><td><b>{V['precB']}</b><span>{V['revBi']} to people · $0 · {V['latB']} s</span></td></tr>
  <tr><td>Photos</td><td><b>{V['wA']}</b><span>{V['wArev']} to people</span></td><td><b>{V['wB']}</b><span>{V['wBrev']} to people</span></td></tr>
</table></div>
<p>On phone photos the two modes are within sampling noise of each other ({V['wgapB']} points, 95% interval {V['wgapB_ci']}) and differ in review load; on scans local only gives up {V['scan_gap']} points. <b>Keeping data in costs mostly people's time.</b></p>
<p>In cloud mode the image leaves the machine at one step only; every check and routing decision runs locally.</p>
<p>Check rules are per domain: a check tuned on scan errors caught {V['d_caught']} of {V['leak_other']} there with no false alarms, but {V['d_wild_caught_rcpt']} receipt on held-out photos, with {V['d_wild_false_rcpt']} false alarm.</p>
<div class="lbl">Next</div>
<p>10k receipts; invoices and statements; layout features for the hand-off decision; a weekly drift metric; a local name detector before any cloud step (masking by rules was tested after the poster, below).</p>

<h2 id="after"><span class="n">+</span>After the poster</h2>
<p class="ans">Error bars, people's time, and the misses.</p>

<h3>How sure are these numbers?</h3>
<p>One run, so the measurable uncertainty is which receipts were sampled: 95% bootstrap intervals, {V['boot_B']} resamples, policies compared on the same resample.</p>
<div class="tablewrap"><table class="cmp small">
  <tr><th></th><th>Harness</th><th>All cloud</th><th>Local only</th></tr>
  <tr><td>Scans</td><td><b>{V['precA']}</b><span>{V['ciA']}</span></td><td><b>{V['aT3']}</b><span>{V['ciT3']}</span></td><td><b>{V['precB']}</b><span>{V['ciB']}</span></td></tr>
  <tr><td>Photos</td><td><b>{V['wA']}</b><span>{V['wciA']}</span></td><td><b>{V['wT3']}</b><span>{V['wciT3']}</span></td><td><b>{V['wB']}</b><span>{V['wciB']}</span></td></tr>
</table></div>
<p>On scans the {V['cloud_gap']}-point gap to all-cloud is {'inside the noise' if V['gapA_zero'] else 'outside the noise'} (interval {V['gapA_ci']} points); the {V['scan_gap']}-point gap to local only is {'inside the noise' if V['gapB_zero'] else 'real'} ({V['gapB_ci']}). <b>The harness matches all-cloud accuracy; it does not beat it.</b></p>

<h3>Counting people's time</h3>
<p>Assumption, not measurement: {V['review_min']} min per reviewed receipt at ${V['review_wage']}/h (${V['review_usd']} per review). Per 1,000 scanned receipts:</p>
<div class="tablewrap"><table class="cmp small">
  <tr><th></th><th>API</th><th>People</th><th>Total</th></tr>
  <tr><td>All cloud, cheap</td><td>${V['cT3']}</td><td>$0.00</td><td><b>${V['totT3']}</b></td></tr>
  <tr><td>Harness</td><td>${V['costA']}</td><td>${V['peopleA']}</td><td><b>${V['totA']}</b></td></tr>
  <tr><td>Local only</td><td>$0.00</td><td>${V['peopleB']}</td><td><b>${V['totB']}</b></td></tr>
</table></div>
<p>The API saving is real but small: a review would have to cost under ${V['breakeven_usd']} ({V['breakeven_s']} s of a person's time) for the harness to be cheaper overall. <b>Its case is where the images go ({V['t1i']} stay on the machine), not price.</b></p>

<h3>Hiding personal data before the cloud call</h3>
<p>When the local reader fails, hide the personal data on this machine, then let the cloud read the masked image. 30 cloud-bound receipts per dataset, each read as the original and as the masked image by the same model; differences in points, masked minus original.</p>
<div class="tablewrap"><table class="cmp small">
  <tr><th></th><th>Personal items hidden</th><th>Date + total, points</th><th>To people, points</th></tr>
  <tr><td>Field rules, scans</td><td><b>{V['pii_r0_hidden']}</b></td><td>{V['pii_r0_t3']}</td><td>{V['pii_r0_review']}</td></tr>
  <tr><td>Allowlist, scans</td><td><b>{V['pii_rev1_hidden']}</b></td><td>{V['pii_rev1_t3']}</td><td>{V['pii_rev1_review']}</td></tr>
  <tr><td>Field rules, photos</td><td><b>{V['wpii_r0_hidden']}</b></td><td>{V['wpii_r0_t3']}</td><td>{V['wpii_r0_review']}</td></tr>
  <tr><td>Allowlist, photos</td><td><b>{V['wpii_rev1_hidden']}</b></td><td>{V['wpii_rev1_t3']}</td><td>{V['wpii_rev1_review']}</td></tr>
</table></div>
<p><b>Field rules missed most names; hiding everything but dates and amounts cost accuracy and sent almost every receipt to people.</b> Local-only stays the answer when data cannot leave. Model-labeled (Gemini 3.1 Flash-Lite), 30 receipts per dataset, rules frozen before any label; details and caveats in the README.</p>

<h3>What catches the misses?</h3>
<p>In cloud mode {V['bs_leaksA']} of {V['n']} scans are wrong yet pass every check; {V['bs_small']} are off by under 0.10. A random 5% audit catches about 5% of them; its job is to measure the miss rate (in this run it finds at least one with probability {V['bs_audit'][1]['p_find']}). Re-reading the top 20% by amount with the strong model finds {V['bs_recheck'][2]['caught']}; re-reading everything finds {V['bs_recheck'][-1]['caught']} of {V['bs_recheck'][-1]['of']} for ${V['bs_recheck'][-1]['usd_1k']} more per 1,000.</p>

<h3 id="correction">Corrected after printing</h3>
<p>The parser that turns printed text into dates and amounts misread four-digit totals without a comma (<code>1039.00</code> as 103), decimal commas, <code>Jul28'15</code> years and dates glued to a time. It fixed {V['wild_fixed_values']} answer-key labels on {V['wild_fixed_receipts']} phone photos (scans: none) and T1's reading of dates. T1's own date is now also checked before it is accepted. The poster PDF is unchanged.</p>
<details{' open' if len(CORR) <= 6 else ''}><summary>{len(CORR)} printed numbers that moved</summary>
<div class="tablewrap"><table class="cmp small">
  <tr><th>Number</th><th>Printed</th><th>Now</th></tr>
  {''.join(f'<tr><td>{e(r["label"])}</td><td>{e(r["printed"])}</td><td><b>{e(r["now"])}</b></td></tr>' for r in CORR)}
</table></div></details>

<footer>
  <div>{V['n']} scanned receipts (ICDAR 2019 SROIE) · {V['n_wild']} phone photos (WildReceipt) · {V['synth_n']} synthetic adversarial receipts. Date and total must match exactly; scoring is code, never a model. Run of 2026-10-31.</div>
  <div>More: <a href="workflow_en.html">step-by-step flow</a> · <a href="workflow_kr.html">한국어 흐름</a> · <a href="companion.html">tablet board (한국어)</a> · <a href="{REPO}">code and every result</a></div>
  <div>Sources: ICDAR 2019 SROIE (Huang et al., arXiv:2103.10213), CC-BY-4.0 · WildReceipt (Sun et al., arXiv:2103.14470) · Tesseract 5.4, RapidOCR / PP-OCR, Qwen2.5-VL (Apache 2.0) via Ollama · Google Gemini API pricing page, 2026-10-31 · fallback chain and sanitizer adapted from the author's open-source boda (MIT). Production figures are from the author's 2026 engagement; the platform is private.</div>
</footer>
</div></body></html>"""

(ROOT / "docs" / "index.html").write_text(page, encoding="utf-8")
print("wrote docs/index.html and docs/assets/")
