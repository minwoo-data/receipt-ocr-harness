"""15_companion.py - Build docs/companion.html, a four-panel board for a tablet.

Layout rules (so sizes stay proportional on any screen):
  - the board fills the viewport (2 x 2 panels); phones (< 700 px wide) get one
    column that scrolls as a page
  - one base font size, set from the viewport area (sqrt(w*h) / 90, clamped
    11-18 px); everything inside a panel is sized in em, so text, ladder,
    tables and captions scale together
  - figures fit the panel height (container query units), stacked; both are
    wide-format charts
  - tap a panel title to open that panel full screen (Esc or tap again to close)

Panels: 1 summary + results, 2 intake flow (HTML ladder; the Mermaid version
stays in docs/OVERVIEW.ko.md), 3 the two poster figures (outcomes first), 4 production prompt
experiment + data-residency checklist + 10k + hedging figure.
    python scripts/15_companion.py
"""
import base64, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
md = (ROOT / "docs" / "OVERVIEW.ko.md").read_text(encoding="utf-8")
parts = re.split(r"^## ", md, flags=re.M)
sec = {p.split("\n", 1)[0].strip(): "## " + p for p in parts[1:]}
def pick(*names):
    missing = [n for n in names if n not in sec]
    assert not missing, f"OVERVIEW.ko.md is missing sections: {missing}"
    return "\n".join(sec[n] for n in names)
q1 = pick("한 문단 요약", "결과 핵심 (스캔 300장, date + total exact)")
q2 = re.sub(r"```mermaid\n.*?```\n*", "", pick("영수증 한 장이 들어오면 (flow)"), flags=re.S)   # ladder below replaces the chart
q4 = pick("프로덕션에서 했던 40장 prompt 실험 (2026-04, Accuver)", "데이터 반출 제약이 있을 때 확인할 것", "10k 로 갈 때")

# Same steps as the Mermaid flow in OVERVIEW.ko.md: (css class, reader, detail, check, on fail)
LADDER = [
    ("t1", "T1 로컬 OCR + rules", "RapidOCR 텍스트 + Tesseract witness, rules 로 vendor / date / total",
     "두 OCR 의 date + total 일치 AND OCR confidence ≥ τ ?", "아니오"),
    ("t2", "T2 로컬 VLM", "Qwen2.5-VL 3B (Ollama), 클라우드와 같은 prompt + JSON schema", "코드 검증 1-4 플래그 0 ?", "플래그"),
    ("t3", "T3 클라우드 cheap", "Gemini 3.1 Flash-Lite", "코드 검증 1-4 플래그 0 ?", "플래그"),
    ("t4", "T4 클라우드 strong", "Gemini 3.6 Flash, thinking off, vendor failover to Claude", "코드 검증 1-4 플래그 0 ?", "플래그"),
]
def ladder():
    rows = ['<div class="lad"><div class="pill">Receipt image intake</div><div class="dn">↓</div>']
    for cls, name, detail, check, fail in LADDER:
        rows.append(f'<div class="row"><div class="rd {cls}"><b>{name}</b> · {detail}</div><div class="ar">→</div>'
                    f'<div class="ck">{check}</div><div class="ar">예 →</div><div class="pill acc">AUTO-ACCEPT</div></div>'
                    f'<div class="dn">↓ {fail}</div>')
    rows.append('<div class="pill rev">HUMAN REVIEW</div>'
                '<div class="ft">코드 검증 1-4 = sanitizer · arithmetic · date plausibility · two-reader. '
                '표적 재시도(플래그된 필드만 한 번 다시 읽고 코드가 더 나은 후보를 고름)는 어느 검증에서든 선택적.</div></div>')
    return "".join(rows)

def img(name):
    f = ROOT / "results" / "figures" / name
    assert f.exists(), f"missing figure {f}"
    return f'<img src="data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()}" alt="{name}">'

CSS = """
 html,body{margin:0;height:100%}
 body{background:#fff;font-family:Arial,"Malgun Gothic",sans-serif;color:#0b0b0b;line-height:1.42}
 .board{position:fixed;inset:0;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:.6rem;padding:.6rem;box-sizing:border-box}
 .q{container-type:size;overflow:auto;min-height:0;min-width:0;border:1px solid #e1e0d9;border-radius:.6rem;padding:.8em 1em;font-size:1rem;background:#fff}
 .q > h2{margin:0 0 .45em;font-size:1.15em;letter-spacing:.02em;border-bottom:.14em solid #0b0b0b;padding-bottom:.2em;cursor:pointer}
 .q > h2 .n{display:inline-block;width:1.4em;height:1.4em;border-radius:50%;background:#0b0b0b;color:#fff;text-align:center;line-height:1.4em;font-size:.8em;margin-right:.45em;vertical-align:.08em}
 .q > h2 .hint{float:right;font-size:.68em;font-weight:normal;color:#898781;margin-top:.35em}
 .md h2,.md h3{font-size:1.02em;margin:.75em 0 .3em;border:0}
 .md p{margin:.4em 0}
 table{border-collapse:collapse;width:100%;font-size:.9em;margin:.3em 0} th,td{border-bottom:1px solid #e1e0d9;padding:.28em .45em;text-align:left;vertical-align:top}
 th{color:#52514e;font-weight:normal;font-size:.88em}
 .figs{display:grid;grid-template-columns:1fr;gap:.6em;justify-items:center}
 .figs figure{margin:0;text-align:center}
 .figs img{display:block;margin:0 auto;width:auto;height:auto;max-width:100%;max-height:calc(50cqh - 3.4em)}   /* both figures are wide: always stacked */
 figcaption{color:#52514e;font-size:.82em;margin-top:.2em}
 .q4fig img{display:block;margin:.4em auto;max-width:100%;max-height:60cqh;width:auto;height:auto}
 .lad{background:#f3f2ee;border-radius:.5em;padding:.6em .75em;font-size:.92em;line-height:1.3}
 .lad .row{display:grid;grid-template-columns:1fr auto .8fr auto auto;align-items:center;gap:.45em}
 .lad .rd{border:.12em solid;border-radius:.3em;padding:.25em .55em} .lad .ck{background:#fff;border:1px dashed #898781;border-radius:.3em;padding:.25em .55em}
 .lad .ar{color:#52514e;white-space:nowrap} .lad .dn{color:#52514e;padding:0 0 0 1.8em;font-size:.9em;line-height:1.25}
 .lad .pill{display:inline-block;border:.12em solid #898781;border-radius:999px;padding:.12em .75em;background:#fff;font-size:.9em;white-space:nowrap;justify-self:start}
 .lad .acc{background:#e3f6e3;border-color:#0ca30c} .lad .rev{background:#f0f1f2;border-color:#6b7079}
 .lad .t1{background:#dce9fa;border-color:#2a78d6} .lad .t2{background:#eaf3fd;border-color:#8cb9ee} .lad .t3{background:#fde3d6;border-color:#eb6834} .lad .t4{background:#fdeee5;border-color:#f5ad83}
 .lad .ft{color:#52514e;font-size:.85em;margin-top:.4em}
 .q.full{position:fixed;inset:.6rem;z-index:10;font-size:1.3rem;box-shadow:0 .3rem 1.6rem rgba(0,0,0,.25)}
 @media (max-width:700px){
   .board{position:static;display:block}
   .q{container-type:normal;overflow:visible;margin-bottom:.6rem}
   .figs img{max-height:none} .q4fig img{max-height:none}
   .q.full{position:static;font-size:1rem;box-shadow:none}
   .lad .row{grid-template-columns:1fr auto auto}
   .lad .row .ck{grid-column:1 / -1;order:3}
 }
"""

html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>receipt-ocr-harness companion</title>
<style>{CSS}</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script></head>
<body><div class="board">
 <section class="q"><h2><span class="n">1</span>요약과 결과</h2><div class="md" data-src="q1"></div></section>
 <section class="q"><h2><span class="n">2</span>영수증 한 장의 흐름</h2>{ladder()}<div class="md" data-src="q2"></div></section>
 <section class="q"><h2><span class="n">3</span>그림</h2><div class="figs">
   <figure>{img("fig_outcomes.png")}<figcaption>정책별로 영수증이 어디서 끝나는지, 정확도와 1k 장당 비용.</figcaption></figure>
   <figure>{img("fig_sweep.png")}<figcaption>Escalation curve: 클라우드로 보낸 비율 vs 자동승인 정확도. 별 = oracle.</figcaption></figure>
 </div></section>
 <section class="q"><h2><span class="n">4</span>프로덕션 실험과 운영 체크리스트</h2><div class="md" data-src="q4"></div>
   <figure class="q4fig">{img("fig_hedge_results.png")}<figcaption>Hedging: time budget D vs 클라우드로 간 비율.</figcaption></figure></section>
</div>
<script>
// One base size for the whole board, from the viewport area; panels size everything in em.
function scale() {{
  const w = innerWidth, h = innerHeight;
  const f = w < 700 ? 15 : Math.max(11, Math.min(18, Math.sqrt(w * h) / 90));
  document.documentElement.style.fontSize = f.toFixed(2) + 'px';
}}
scale(); addEventListener('resize', scale);
const S = {json.dumps({"q1": q1, "q2": q2, "q4": q4}, ensure_ascii=False)};
for (const el of document.querySelectorAll('.md')) {{
  const src = S[el.dataset.src].replace(/^## .*$/m, '');
  el.innerHTML = marked.parse(src);
}}
// Tap a panel title to open that panel full screen; tap again (or Esc) to go back.
const closeAll = () => document.querySelectorAll('.q.full').forEach(x => x.classList.remove('full'));
for (const h of document.querySelectorAll('.q > h2')) {{
  h.insertAdjacentHTML('beforeend', '<span class="hint">탭: 크게</span>');
  h.addEventListener('click', () => {{ if (innerWidth < 700) return; const q = h.parentElement, on = !q.classList.contains('full'); closeAll(); if (on) q.classList.add('full'); }});
}}
addEventListener('keydown', e => {{ if (e.key === 'Escape') closeAll(); }});
</script></body></html>"""
out = ROOT / "docs" / "companion.html"; out.write_text(html, encoding="utf-8"); print("wrote", out.name, out.stat().st_size // 1024, "KB")
