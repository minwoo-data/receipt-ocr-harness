"""15_companion.py - Build docs/companion.html as an A3-landscape board of four
equal quadrants (summary | intake flow | results | figures) for a tablet.
Markdown renders in the browser (cdnjs); figures are embedded. The intake flow
is drawn as a compact HTML ladder (tier | check | outcome) so it fits a quadrant;
the Mermaid version stays in docs/OVERVIEW.ko.md. Tap a panel title to open it
full screen.
    python scripts/15_companion.py
"""
import base64, json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
md = (ROOT / "docs" / "OVERVIEW.ko.md").read_text(encoding="utf-8")
parts = re.split(r"^## ", md, flags=re.M)
sec = {p.split("\n", 1)[0].strip(): "## " + p for p in parts[1:]}
def pick(*names):
    return "\n".join(sec[n] for n in names if n in sec)
q1 = pick("한 문단 요약") + "\n\n" + sec.get("읽는 순서 제안", "")
q2 = re.sub(r"```mermaid\n.*?```\n*", "", pick("영수증 한 장이 들어오면 (flow)"), flags=re.S)   # ladder below replaces the chart
q3 = pick("결과 핵심 (스캔 300장, date + total exact)", "프로덕션에서 했던 40장 prompt 실험 (2026-04, Accuver)")
q4_md = pick("데이터 반출 제약이 있을 때 확인할 것", "10k 로 갈 때")

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
    return f'<img src="data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()}" alt="{name}">' if f.exists() else ""
html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>receipt-ocr-harness companion</title>
<style>
 body{{margin:0;background:#e9e8e3;font-family:Arial,"Malgun Gothic",sans-serif;color:#0b0b0b;line-height:1.45}}
 .board{{width:min(100vw,calc(100vh*1.414));height:min(100vh,calc(100vw/1.414));margin:0 auto;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:8px;padding:8px;box-sizing:border-box;background:#fff}}
 .q{{overflow:auto;border:1px solid #e1e0d9;border-radius:8px;padding:12px 14px;font-size:13px;min-height:0}}
 .q h2{{margin:0 0 6px 0;font-size:15px;text-transform:uppercase;letter-spacing:.3px;border-bottom:2px solid #0b0b0b;padding-bottom:3px}}
 .q h2 .n{{display:inline-block;width:18px;height:18px;border-radius:50%;background:#0b0b0b;color:#fff;text-align:center;line-height:18px;font-size:11px;margin-right:6px}}
 .q h3,.q .md h2{{font-size:13.5px;margin:10px 0 4px 0;border:0;text-transform:none;letter-spacing:0}}
 table{{border-collapse:collapse;width:100%;font-size:12px}} th,td{{border-bottom:1px solid #e1e0d9;padding:4px 6px;text-align:left;vertical-align:top}} th{{color:#52514e;font-weight:normal;font-size:11px;text-transform:uppercase}}
 img{{max-width:100%;height:auto;display:block;margin:4px auto}} figcaption{{color:#52514e;font-size:11.5px;text-align:center;margin-bottom:8px}}
 .lad{{background:#f3f2ee;border-radius:8px;padding:8px 10px;font-size:12px;line-height:1.3}}
 .lad .row{{display:grid;grid-template-columns:1fr auto 0.8fr auto auto;align-items:center;gap:6px}}
 .lad .rd{{border:1.5px solid;border-radius:4px;padding:3px 7px}} .lad .ck{{background:#fff;border:1px dashed #898781;border-radius:4px;padding:3px 7px}}
 .lad .ar{{color:#52514e;white-space:nowrap}} .lad .dn{{color:#52514e;padding:0 0 0 24px;font-size:11px;line-height:1.25}}
 .lad .pill{{display:inline-block;border:1.5px solid #898781;border-radius:999px;padding:2px 10px;background:#fff;font-size:11.5px;white-space:nowrap;justify-self:start}}
 .lad .acc{{background:#e3f6e3;border-color:#0ca30c}} .lad .rev{{background:#fae0e0;border-color:#d03b3b}}
 .lad .t1{{background:#dce9fa;border-color:#2a78d6}} .lad .t2{{background:#fde3d6;border-color:#eb6834}} .lad .t3{{background:#d9f3e9;border-color:#1baf7a}} .lad .t4{{background:#fbefcf;border-color:#eda100}}
 .lad .ft{{color:#52514e;font-size:11px;margin-top:5px}}
 .q > h2{{cursor:pointer}} .q > h2 .hint{{float:right;font-size:11px;font-weight:normal;color:#898781;text-transform:none;letter-spacing:0}}
 .q.full{{position:fixed;inset:8px;z-index:10;background:#fff;box-shadow:0 4px 24px rgba(0,0,0,.25);font-size:15px}}
 .q.full .lad{{font-size:15px}} .q.full table{{font-size:14px}}
 @media (max-width:700px){{.board{{width:100%;height:auto;grid-template-columns:1fr;grid-template-rows:none}} .q{{max-height:90vh}}}}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script></head>
<body><div class="board">
 <section class="q"><h2><span class="n">1</span>요약</h2><div class="md" data-src="q1"></div></section>
 <section class="q"><h2><span class="n">2</span>영수증 한 장의 흐름</h2>{ladder()}<div class="md" data-src="q2"></div></section>
 <section class="q"><h2><span class="n">3</span>결과와 prompt 실험</h2><div class="md" data-src="q3"></div></section>
 <section class="q"><h2><span class="n">4</span>그림과 운영 체크리스트</h2>
   <figure>{img("fig_sweep.png")}<figcaption>Escalation curve: cloud share vs accepted precision. Star = oracle.</figcaption></figure>
   <figure>{img("fig_outcomes.png")}<figcaption>Where each receipt ends up, by policy.</figcaption></figure>
   <figure>{img("fig_hedge_results.png")}<figcaption>Hedging: time budget D vs cloud share.</figcaption></figure>
   <div class="md" data-src="q4"></div></section>
</div>
<script>
const S = {json.dumps({"q1": q1, "q2": q2, "q3": q3, "q4": q4_md}, ensure_ascii=False)};
for (const el of document.querySelectorAll('.md')) {{
  const src = S[el.dataset.src].replace(/^## .*$/m, '');
  el.innerHTML = marked.parse(src);
}}
// Tap a panel title to open that panel full screen; tap again (or Esc) to go back.
const closeAll = () => document.querySelectorAll('.q.full').forEach(x => x.classList.remove('full'));
for (const h of document.querySelectorAll('.q > h2')) {{
  h.insertAdjacentHTML('beforeend', '<span class="hint">탭: 크게 / 다시 탭: 원래대로</span>');
  h.addEventListener('click', () => {{ const q = h.parentElement, on = !q.classList.contains('full'); closeAll(); if (on) q.classList.add('full'); }});
}}
addEventListener('keydown', e => {{ if (e.key === 'Escape') closeAll(); }});
</script></body></html>"""
out = ROOT / "docs" / "companion.html"; out.write_text(html, encoding="utf-8"); print("wrote", out.name, out.stat().st_size // 1024, "KB")
