"""15_companion.py - Build docs/companion.html: the Korean overview (with the
mermaid intake flow) plus the poster figures, as ONE html file for a tablet.
Markdown and mermaid render in the browser (marked.js, mermaid.js from cdnjs /
jsdelivr), figures are embedded as base64 so the file travels alone.
    python scripts/15_companion.py
"""
import base64, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
md = (ROOT / "docs" / "OVERVIEW.ko.md").read_text(encoding="utf-8")
figs = []
for name, cap in (("fig_sweep.png", "Escalation curve: cloud share vs accepted precision; star = oracle"),
                  ("fig_outcomes.png", "Where each receipt ends up, by policy"),
                  ("fig_waterfall.png", "Model errors caught by code, per tier"),
                  ("fig_hedge_results.png", "Hedging: time budget vs cloud share (SROIE)")):
    f = ROOT / "results" / "figures" / name
    if f.exists():
        figs.append(f'<figure><img src="data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()}" alt="{cap}"><figcaption>{cap}</figcaption></figure>')
html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>receipt-ocr-harness companion</title>
<style>body{{font-family:Arial,"Malgun Gothic",sans-serif;max-width:900px;margin:0 auto;padding:16px;line-height:1.5;color:#0b0b0b;background:#fff}}
table{{border-collapse:collapse;width:100%;font-size:14px}} th,td{{border-bottom:1px solid #e1e0d9;padding:6px 8px;text-align:left;vertical-align:top}} th{{color:#52514e;font-weight:normal;text-transform:uppercase;font-size:12px}}
figure{{margin:20px 0}} img{{max-width:100%;height:auto}} figcaption{{color:#52514e;font-size:13px}} h1,h2{{letter-spacing:-0.2px}} .mermaid{{background:#f3f2ee;border-radius:8px;padding:10px}}
nav a{{margin-right:12px;font-size:14px}}</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script></head>
<body><nav><a href="#top">요약</a><a href="#figs">그림</a></nav><div id="top"></div><div id="md"></div>
<h2 id="figs">그림 (SROIE 300, 2026-10-31 실행)</h2>{''.join(figs)}
<script>
const src = {json.dumps(md)};
const html = marked.parse(src.replace(/```mermaid
([\s\S]*?)```/g, (m, g) => '<pre class="mermaid">' + g + '</pre>'));
document.getElementById('md').innerHTML = html;
mermaid.initialize({{startOnLoad: false, theme: 'neutral'}}); mermaid.run({{querySelector: '.mermaid'}});
</script></body></html>"""
out = ROOT / "docs" / "companion.html"
out.write_text(html, encoding="utf-8")
print("wrote", out, f"{out.stat().st_size // 1024} KB")
