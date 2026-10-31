"""15_companion.py - Build docs/companion.html as an A3-landscape board of four
equal quadrants (summary | intake flow | results | figures) for a tablet.
Markdown + mermaid render in the browser (cdnjs / jsdelivr); figures embedded.
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
q2 = pick("영수증 한 장이 들어오면 (flow)")
q3 = pick("결과 핵심 (스캔 300장, date + total exact)", "프로덕션에서 했던 40장 prompt 실험 (2026-04, Accuver)")
q4_md = pick("데이터 반출 제약이 있을 때 확인할 것", "10k 로 갈 때")
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
 .q h3,.q h2.md{{font-size:13.5px;margin:10px 0 4px 0;border:0}}
 table{{border-collapse:collapse;width:100%;font-size:12px}} th,td{{border-bottom:1px solid #e1e0d9;padding:4px 6px;text-align:left;vertical-align:top}} th{{color:#52514e;font-weight:normal;font-size:11px;text-transform:uppercase}}
 img{{max-width:100%;height:auto;display:block;margin:4px auto}} figcaption{{color:#52514e;font-size:11.5px;text-align:center;margin-bottom:8px}}
 .mermaid{{background:#f3f2ee;border-radius:8px;padding:6px}}
 @media (max-width:700px){{.board{{width:100%;height:auto;grid-template-columns:1fr;grid-template-rows:none}} .q{{max-height:90vh}}}}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script></head>
<body><div class="board">
 <section class="q"><h2><span class="n">1</span>요약</h2><div class="md" data-src="q1"></div></section>
 <section class="q"><h2><span class="n">2</span>영수증 한 장의 흐름</h2><div class="md" data-src="q2"></div></section>
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
  el.innerHTML = marked.parse(src.replace(/```mermaid\n([\s\S]*?)```/g, (m, g) => '<pre class="mermaid">' + g + '</pre>'));
}}
mermaid.initialize({{startOnLoad:false, theme:'neutral'}}); mermaid.run({{querySelector:'.mermaid'}});
</script></body></html>"""
out = ROOT / "docs" / "companion.html"; out.write_text(html, encoding="utf-8"); print("wrote", out.name, out.stat().st_size // 1024, "KB")
