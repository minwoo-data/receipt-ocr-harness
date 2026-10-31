"""16_workflow_pages.py - docs/workflow_en.html and docs/workflow_kr.html.

Three layers, top to bottom:
  1. Architecture at a glance (inline SVG, AWS-diagram style): boundaries for
     the local machine, Google Gemini API and Anthropic API; the harness in the
     middle calls each reader; numbered steps with a legend; KPI cards per mode.
  2. How one receipt moves: compact Mermaid decision flows (tier + share only).
  3. Details (muted): reader specs, code-check definitions, what the checks
     caught, photos, the oracle gap.
Must-see items (tier, share, outcome, KPIs) are large and dark; supporting
detail (models, latency, cost, rules) is small and grey.

Every number comes from results/harness/policies.json, results/harness/waterfall.json
and results_wild/harness/policies.json (SROIE 300 / WildReceipt 200).
    python scripts/16_workflow_pages.py
"""
import html as H
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "src"))
from harness.report_numbers import numbers  # noqa: E402  (one number source with the poster and landing page)

V = numbers()
N = V["n"]

T = {
 "en": dict(
   title="Receipt OCR harness: architecture and flow",
   sub=f"Numbers: {N} SROIE scans, date + total exact match, run of 2026-10-31. Model self-confidence is never used to approve.",
   s1="1 · Architecture at a glance", s2="2 · How one receipt moves", s3="3 · Details",
   bLocal="Your machine · receipts and checks stay here", bGem="Google Gemini API · cloud", bAnt="Anthropic API · fallback only",
   img=("Receipt", "image"),
   T1=("T1 · Local OCR + rules", "RapidOCR + Tesseract witness", f"alone {V['aT1']} · {V['sT1']} s · $0"),
   T2=("T2 · Local VLM", "Qwen2.5-VL 3B via Ollama", f"alone {V['aT2']} · {V['sT2']} s · $0"),
   T3=("T3 · Cloud, cheap", "Gemini 3.1 Flash-Lite", f"alone {V['aT3']} · {V['sT3']} s · ${V['cT3']} / 1k"),
   T4=("T4 · Cloud, strong", "Gemini 3.6 Flash, thinking off", f"alone {V['aT4']} · {V['sT4']} s · ${V['cT4']} / 1k"),
   CL=("Claude Haiku", "vendor failover", "production design; no key in this run"),
   HAR=("Harness: router + code checks", "decides every step, on this machine", "model self-confidence never approves"),
   ACC=("Auto-accept", f"A {V['accA']} · B {V['accB']}", f"of {N} receipts"),
   REV=("Human review", f"A {V['revA']} · B {V['revB']}", f"A {V['nrevA']} · B {V['nrevB']} receipts"),
   lbl=dict(ok="pass", still="still flagged", leaves="image leaves", local="local only", fb="Gemini 429 / 503"),
   steps=[
     ("1", "Receipt image arrives", "file check, resized (1,600 px for cloud, 1,024 px for the local VLM)"),
     ("2", "T1 reads every receipt, locally", "RapidOCR text, Tesseract as a second witness, rules pull vendor / date / total"),
     ("3", f"T1 sure → auto-accept · {V['t1']}", "both OCR readers agree on date and total AND OCR confidence ≥ 0.9"),
     ("4", f"Not sure → T3 Gemini Flash-Lite · {V['sent']}", f"the only step where the image leaves the machine; code checks pass → auto-accept ({V['t3']})"),
     ("5", f"Checks flag T3 → T4 Gemini Flash · {V['toT4']}", f"zero flags → auto-accept ({V['t4']})"),
     ("6", f"Still flagged → human review · {V['revA']}", f"{V['nrevA']} of {N} receipts"),
     ("B", f"Local only: step 4 goes to T2 Qwen2.5-VL · {V['sent']}", f"zero flags → auto-accept ({V['t2']}); flagged → human review ({V['revB']})"),
     ("⚡", "Gemini 429 / 503 → Claude Haiku", "one fast-fail attempt, circuit breaker after 3 failures, 60 s cooldown"),
   ],
   kA="A. Cloud available", kB="B. Local only (no data leaves the machine)",
   kcap=["accepted answers correct", "to human review", "sent to the cloud", "per 1k receipts", "median per receipt"],
   fA="A. Cloud available", fB="B. Local only",
   m=dict(img="Receipt image", t1="T1 · RapidOCR + rules", sure="T1 sure?", t3="T3 · Gemini 3.1 Flash-Lite", t4="T4 · Gemini 3.6 Flash",
          t2="T2 · Qwen2.5-VL 3B (local)", chk="checks 1-4 pass?", acc="AUTO-ACCEPT", rev="HUMAN REVIEW", yes="yes", no="no"),
   spec_h=["Tier", "Reader", "Runs on", "Alone: date + total exact", "Median", "USD / 1k"],
   spec=[("T1", "RapidOCR + rules (Tesseract witness)", "local CPU"), ("T2", "Qwen2.5-VL 3B via Ollama", "local GPU (RTX 2050, Vulkan)"),
         ("T3", "Gemini 3.1 Flash-Lite", "Google cloud"), ("T4", "Gemini 3.6 Flash, thinking off", "Google cloud")],
   notes=[
     ("Code checks 1-4 (no answer key)", "<ol><li>sanitizer: NFKC, EN/KO/JA/ZH injection patterns, field whitelist, types</li><li>arithmetic: subtotal + tax + tip + discount = total (tolerance 0.05; absent is not zero)</li><li>date plausible for the dataset era</li><li>two-reader: the model's total and date must appear in the OCR text</li></ol>"),
     ("What the checks caught", f"Each reader run alone on all {N}: the checks flagged {V['c3']} of Flash-Lite's {V['e3']} wrong answers, {V['c4']} of Flash's {V['e4']}, and {V['c2']} of the local VLM's {V['e2']}."),
     ("The hard part is knowing when to call the cloud", f"An oracle that knows the answers sends {V['oracle_cloud']} to the cloud for {V['oracle_prec']}. The rule signal sends {V['router_cloud']} for {V['router_prec']} (no checks)."),
     ("Phone photos (WildReceipt 200)", f"Cloud harness {V['wA']} with {V['wArev']} review; local only {V['wB']} with {V['wBrev']} review. Same accuracy, different review load."),
   ]),
 "kr": dict(
   title="영수증 OCR 하네스: 구조와 흐름",
   sub=f"숫자: SROIE 스캔 {N}장, 날짜 + 총액 exact match, 2026-10-31 실행. 모델의 self-reported confidence 는 승인에 쓰지 않습니다.",
   s1="1 · 한눈에 보는 구조", s2="2 · 영수증 한 장의 흐름", s3="3 · 자세히",
   bLocal="로컬 머신 · 영수증과 검증은 여기 머묾", bGem="Google Gemini API · 클라우드", bAnt="Anthropic API · 장애 때만",
   img=("영수증", "이미지"),
   T1=("T1 · 로컬 OCR + 규칙", "RapidOCR + Tesseract 증인", f"단독 {V['aT1']} · {V['sT1']}초 · $0"),
   T2=("T2 · 로컬 VLM", "Qwen2.5-VL 3B (Ollama)", f"단독 {V['aT2']} · {V['sT2']}초 · $0"),
   T3=("T3 · 클라우드 cheap", "Gemini 3.1 Flash-Lite", f"단독 {V['aT3']} · {V['sT3']}초 · ${V['cT3']} / 1k"),
   T4=("T4 · 클라우드 strong", "Gemini 3.6 Flash, thinking off", f"단독 {V['aT4']} · {V['sT4']}초 · ${V['cT4']} / 1k"),
   CL=("Claude Haiku", "vendor failover", "프로덕션 설계, 이번 실행엔 키 없음"),
   HAR=("하네스: 라우터 + 코드 검증", "모든 단계를 이 기계에서 판정", "모델 self-confidence 로는 승인 안 함"),
   ACC=("자동승인", f"A {V['accA']} · B {V['accB']}", f"{N}장 중"),
   REV=("사람 검토", f"A {V['revA']} · B {V['revB']}", f"A {V['nrevA']}장 · B {V['nrevB']}장"),
   lbl=dict(ok="통과", still="여전히 플래그", leaves="이미지 반출", local="로컬 전용", fb="Gemini 429 / 503"),
   steps=[
     ("1", "영수증 이미지 입력", "파일 검증 후 축소 (클라우드 1,600px, 로컬 VLM 1,024px)"),
     ("2", "T1 이 모든 영수증을 로컬에서 읽음", "RapidOCR 텍스트 + Tesseract 증인, 규칙으로 vendor / date / total"),
     ("3", f"T1 확신 → 자동승인 · {V['t1']}", "두 OCR 의 날짜·총액 일치 AND OCR confidence ≥ 0.9"),
     ("4", f"확신 없음 → T3 Gemini Flash-Lite · {V['sent']}", f"이미지가 기계를 떠나는 유일한 단계. 코드 검증 통과 → 자동승인 ({V['t3']})"),
     ("5", f"T3 플래그 → T4 Gemini Flash · {V['toT4']}", f"플래그 0 → 자동승인 ({V['t4']})"),
     ("6", f"여전히 플래그 → 사람 검토 · {V['revA']}", f"{N}장 중 {V['nrevA']}장"),
     ("B", f"로컬 전용: 4단계가 T2 Qwen2.5-VL 로 · {V['sent']}", f"플래그 0 → 자동승인 ({V['t2']}), 플래그 → 사람 검토 ({V['revB']})"),
     ("⚡", "Gemini 429 / 503 → Claude Haiku", "fast-fail 1회, 연속 3회 실패 시 circuit breaker 60초"),
   ],
   kA="A. 클라우드 가능", kB="B. 로컬 전용 (데이터 반출 없음)",
   kcap=["자동승인 정확도", "사람 검토", "클라우드로 보냄", "1k 장당", "장당 중앙값"],
   fA="A. 클라우드 가능", fB="B. 로컬 전용",
   m=dict(img="영수증 이미지", t1="T1 · RapidOCR + 규칙", sure="T1 확신?", t3="T3 · Gemini 3.1 Flash-Lite", t4="T4 · Gemini 3.6 Flash",
          t2="T2 · Qwen2.5-VL 3B (로컬)", chk="검증 1-4 통과?", acc="자동승인", rev="사람 검토", yes="예", no="아니오"),
   spec_h=["Tier", "리더", "실행 위치", "단독: 날짜 + 총액 exact", "중앙값", "USD / 1k"],
   spec=[("T1", "RapidOCR + 규칙 (Tesseract 증인)", "로컬 CPU"), ("T2", "Qwen2.5-VL 3B (Ollama)", "로컬 GPU (RTX 2050, Vulkan)"),
         ("T3", "Gemini 3.1 Flash-Lite", "Google 클라우드"), ("T4", "Gemini 3.6 Flash, thinking off", "Google 클라우드")],
   notes=[
     ("코드 검증 1-4 (정답 없이)", "<ol><li>sanitizer: NFKC, EN/KO/JA/ZH injection 패턴, 필드 화이트리스트, 타입</li><li>arithmetic: subtotal + tax + tip + discount = total (허용오차 0.05, 결측은 0 아님)</li><li>날짜 타당성 (데이터셋 시기 안)</li><li>two-reader: 모델의 총액·날짜가 OCR 텍스트에 있어야 함</li></ol>"),
     ("검증이 잡은 것", f"각 리더를 {N}장 전부에 단독으로 돌렸을 때: Flash-Lite 오답 {V['e3']}건 중 {V['c3']}건, Flash {V['e4']}건 중 {V['c4']}건, 로컬 VLM {V['e2']}건 중 {V['c2']}건을 플래그."),
     ("병목은 신호", f"정답을 아는 오라클은 {V['oracle_cloud']}만 클라우드로 보내고 {V['oracle_prec']}. 규칙 신호는 {V['router_cloud']}를 보내고 {V['router_prec']} (검증 없이)."),
     ("휴대폰 사진 (WildReceipt 200)", f"클라우드 하네스 {V['wA']}, 검토 {V['wArev']}. 로컬 전용 {V['wB']}, 검토 {V['wBrev']}. 정확도는 같고 검토 부담만 다름."),
   ]),
}

# ---------- SVG architecture ----------
COL = {"T1": "#2a78d6", "T2": "#8cb9ee", "T3": "#eb6834", "T4": "#f5ad83", "ok": "#0ca30c", "bad": "#6b7079", "ink": "#0b0b0b",
       "ink2": "#52514e", "mut": "#898781", "line": "#c9c8c2"}
def tw(s, size):                                  # rough text width for Arial / Malgun Gothic
    return sum(size * (1.0 if ord(c) > 0x1100 else 0.56) for c in s)
def esc(s): return H.escape(s, quote=True)
def box(x, y, w, h, color, title, sub=None, aux=None, sub_bold=False):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#fff" stroke="{COL["line"]}" stroke-width="1.2"/>',
           f'<rect x="{x}" y="{y}" width="{w}" height="6" rx="3" fill="{color}"/>',
           f'<text x="{x + 12}" y="{y + 29}" class="bt">{esc(title)}</text>']
    if sub: out.append(f'<text x="{x + 12}" y="{y + 51}" class="{"bsb" if sub_bold else "bs"}">{esc(sub)}</text>')
    if aux: out.append(f'<text x="{x + 12}" y="{y + 72}" class="ba">{esc(aux)}</text>')
    return "".join(out)
def boundary(x, y, w, h, label, color, fill, dash):
    lw = tw(label, 13) * 1.1 + 24                  # bold text runs wider than the estimate
    da = ' stroke-dasharray="7 5"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{color}" stroke-width="1.8"{da}/>'
            f'<rect x="{x}" y="{y}" width="{lw:.0f}" height="26" rx="10" fill="{color}"/><rect x="{x}" y="{y + 13}" width="{lw:.0f}" height="13" fill="{color}"/>'
            f'<text x="{x + 11}" y="{y + 18}" class="bl">{esc(label)}</text>')
def badge(cx, cy, label, color="#0b0b0b"):
    return f'<circle cx="{cx}" cy="{cy}" r="12" fill="{color}"/><text x="{cx}" y="{cy + 4.5}" class="bn">{esc(label)}</text>'
def line(x1, y1, x2, y2, both=False, color="#52514e", dash=False, mk="ah"):
    da = ' stroke-dasharray="6 5"' if dash else ""
    ms = f' marker-start="url(#{mk})"' if both else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.8"{da}{ms} marker-end="url(#{mk})"/>'
def label(x, y, s, cls="lb", anchor="start"):
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{esc(s)}</text>'

def architecture(t):
    L = t["lbl"]; chips = ["1 sanitizer", "2 arithmetic", "3 date", "4 two-reader"]
    hx, hy, hw, hh = 300, 236, 380, 132
    cx = hx + 12; chip_svg = []
    for c in chips:
        w = tw(c, 12) + 16
        chip_svg.append(f'<rect x="{cx:.0f}" y="{hy + 42}" width="{w:.0f}" height="24" rx="5" fill="#f3f2ee" stroke="{COL["line"]}"/>'
                        f'<text x="{cx + 8:.0f}" y="{hy + 58}" class="bc">{esc(c)}</text>')
        cx += w + 7
    parts = [
      boundary(160, 16, 670, 568, t["bLocal"], "#52514e", "#fafaf7", False),
      boundary(866, 16, 280, 356, t["bGem"], "#eb6834", "#fdf3ec", True),
      boundary(866, 404, 280, 180, t["bAnt"], "#898781", "#f6f6f4", True),
      box(14, 250, 128, 100, COL["ink"], t["img"][0], t["img"][1]),
      box(190, 64, 250, 100, COL["T1"], *t["T1"]),
      box(530, 64, 250, 100, COL["T2"], *t["T2"]),
      f'<rect x="{hx}" y="{hy}" width="{hw}" height="{hh}" rx="8" fill="#fff" stroke="{COL["ink"]}" stroke-width="2"/>',
      f'<text x="{hx + 12}" y="{hy + 29}" class="bt">{esc(t["HAR"][0])}</text>', *chip_svg,
      f'<text x="{hx + 12}" y="{hy + 94}" class="ba">{esc(t["HAR"][1])}</text>', f'<text x="{hx + 12}" y="{hy + 113}" class="ba">{esc(t["HAR"][2])}</text>',
      box(190, 476, 250, 86, COL["ok"], *t["ACC"], sub_bold=True),
      box(530, 476, 250, 86, COL["bad"], *t["REV"], sub_bold=True),
      box(886, 66, 244, 100, COL["T3"], *t["T3"]),
      box(886, 236, 244, 100, COL["T4"], *t["T4"]),
      box(886, 456, 244, 100, COL["mut"], *t["CL"]),
      # spokes
      line(142, 300, 298, 300), badge(226, 300, "1"),
      line(355, 234, 318, 166, both=True), badge(337, 200, "2"), label(354, 205, "100%"),
      line(625, 234, 652, 166, both=True, color=COL["T2"], dash=True, mk="ahB"), badge(638, 200, "B", COL["T2"]),
      label(656, 205, V["sent"], "lbB"), label(656, 221, L["local"], "lbs"),
      line(682, 268, 884, 118, both=True, color="#eb6834", mk="ahG"), badge(739, 224, "4"), label(744, 250, V["sent"]), label(744, 265, L["leaves"], "lbs"),
      line(682, 330, 884, 288, both=True, color="#eb6834", mk="ahG"), badge(739, 318, "5"), label(752, 348, V["toT4"]),
      line(1008, 374, 1008, 454, color=COL["mut"], dash=True), label(1018, 394, L["fb"], "lbs"),
      line(395, 370, 320, 474, color=COL["ok"], mk="ahK"), label(366, 432, L["ok"], "lbs", "end"),
      line(585, 370, 650, 474, color=COL["bad"], mk="ahR"), badge(617, 420, "6"), label(634, 440, L["still"], "lbs"),
      badge(hx, hy, "3"),
    ]
    defs = "".join(f'<marker id="{i}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                   f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
                   for i, c in (("ah", "#52514e"), ("ahB", COL["T2"]), ("ahG", "#eb6834"), ("ahK", COL["ok"]), ("ahR", COL["bad"])))
    return (f'<svg class="arch" viewBox="0 0 1160 600" role="img" aria-label="{esc(t["s1"])}"><defs>{defs}</defs>'
            + "".join(parts) + "</svg>")

def mermaid(t, lane):
    m = t["m"]
    head = f'''flowchart LR
  IN(["{m['img']}"]) --> T1["{m['t1']}"]
  T1 --> S{{"{m['sure']}"}}
  S -- "{m['yes']} {V['t1']}" --> A1(["{m['acc']}"])'''
    if lane == "A":
        body = f'''
  S -- "{m['no']} {V['sent']}" --> T3["{m['t3']}"]
  T3 --> G3{{"{m['chk']}"}}
  G3 -- "{m['yes']} {V['t3']}" --> A2(["{m['acc']}"])
  G3 -- "{m['no']} {V['toT4']}" --> T4["{m['t4']}"]
  T4 --> G4{{"{m['chk']}"}}
  G4 -- "{m['yes']} {V['t4']}" --> A3(["{m['acc']}"])
  G4 -- "{m['no']} {V['revA']}" --> R(["{m['rev']}"])
  class T3 t3
  class T4 t4
  class A1,A2,A3 acc'''
    else:
        body = f'''
  S -- "{m['no']} {V['sent']}" --> T2["{m['t2']}"]
  T2 --> G2{{"{m['chk']}"}}
  G2 -- "{m['yes']} {V['t2']}" --> A2(["{m['acc']}"])
  G2 -- "{m['no']} {V['revB']}" --> R(["{m['rev']}"])
  class T2 t2
  class A1,A2 acc'''
    return head + body + '''
  class T1 t1
  class R rev
  classDef t1 fill:#dce9fa,stroke:#2a78d6
  classDef t2 fill:#eaf3fd,stroke:#8cb9ee
  classDef t3 fill:#fde3d6,stroke:#eb6834
  classDef t4 fill:#fdeee5,stroke:#f5ad83
  classDef acc fill:#e3f6e3,stroke:#0ca30c
  classDef rev fill:#f0f1f2,stroke:#6b7079'''

CSS = """
:root{--ink:#0b0b0b;--ink2:#52514e;--mut:#898781;--grid:#e1e0d9;--band:#f6f5f1}
body{margin:0;background:#fff;color:var(--ink);font-family:Arial,"Malgun Gothic",sans-serif;line-height:1.4}
.wrap{max-width:1700px;margin:0 auto;padding:16px 22px 28px}
h1{font-size:26px;margin:0 0 4px} .sub{color:var(--ink2);font-size:14px;margin-bottom:14px}
h2.s{font-size:18px;margin:22px 0 10px;padding-bottom:4px;border-bottom:2px solid var(--ink)}
.top{display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:18px;align-items:start}
svg.arch{width:100%;height:auto;display:block}
svg .bt{font-size:15px;font-weight:bold;fill:#0b0b0b} svg .bs{font-size:13px;fill:#0b0b0b} svg .bsb{font-size:14px;font-weight:bold;fill:#0b0b0b}
svg .ba{font-size:11.5px;fill:#6b6a66} svg .bc{font-size:12px;fill:#0b0b0b} svg .bl{font-size:13px;font-weight:bold;fill:#fff}
svg .bn{font-size:13px;font-weight:bold;fill:#fff;text-anchor:middle}
svg .lb,svg .lbB{font-size:15px;font-weight:bold;fill:#0b0b0b;paint-order:stroke;stroke:#fff;stroke-width:4px} svg .lbB{fill:#3d6fb0}
svg .lbs{font-size:11.5px;fill:#6b6a66;paint-order:stroke;stroke:#fff;stroke-width:3px}
ol.steps{list-style:none;margin:0;padding:0}
ol.steps li{display:grid;grid-template-columns:28px 1fr;gap:2px 8px;padding:7px 0;border-bottom:1px solid var(--grid)}
ol.steps .n{grid-row:span 2;width:24px;height:24px;border-radius:50%;background:var(--ink);color:#fff;font-weight:bold;font-size:13px;display:flex;align-items:center;justify-content:center}
ol.steps .n.b{background:#8cb9ee} ol.steps .n.f{background:var(--mut)}
ol.steps .m{font-size:15px;font-weight:bold} ol.steps .a{font-size:12.5px;color:#6b6a66}
.kpi{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
.kpi .c{border:1.5px solid var(--grid);border-left:6px solid var(--ink);border-radius:10px;padding:10px 14px}
.kpi .c.b{border-left-color:#8cb9ee} .kpi .t{font-size:14.5px;font-weight:bold;margin-bottom:6px}
.kpi .row{display:grid;grid-template-columns:repeat(5,1fr);gap:8px} .kpi .v{font-size:26px;font-weight:bold;line-height:1.1} .kpi .cap{font-size:12px;color:#6b6a66}
.flows{display:grid;gap:12px} .flow{border:1.5px solid var(--grid);border-radius:10px;padding:8px 12px}
.flow h3{margin:0 0 4px;font-size:14.5px} .mermaid .edgeLabel{font-weight:bold}
.det{background:var(--band);border-radius:12px;padding:12px 16px;color:#3d3c39;font-size:13px}
.det table{border-collapse:collapse;width:100%;font-size:13px;margin-bottom:12px} .det th,.det td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--grid)}
.det th{font-weight:normal;color:#6b6a66;font-size:12px;text-transform:uppercase}
.notes{display:grid;grid-template-columns:repeat(4,1fr);gap:10px} .notes div{background:#fff;border:1px solid var(--grid);border-radius:8px;padding:8px 10px}
.notes b{display:block;margin-bottom:3px;color:var(--ink)} .notes ol{margin:0;padding-left:18px}
.foot{color:#6b6a66;font-size:12px;margin-top:12px}
@media (max-width:1100px){.top{grid-template-columns:1fr} .notes{grid-template-columns:1fr 1fr} .kpi{grid-template-columns:1fr}}
"""

def page(lang, t):
    steps = "".join(f'<li><span class="n{" b" if n == "B" else " f" if n == "⚡" else ""}">{esc(n)}</span><span class="m">{esc(mm)}</span><span class="a">{esc(a)}</span></li>'
                    for n, mm, a in t["steps"])
    def kcard(title, cls, vals):
        cells = "".join(f'<div><div class="v">{esc(v)}</div><div class="cap">{esc(c)}</div></div>' for v, c in zip(vals, t["kcap"]))
        return f'<div class="c{cls}"><div class="t">{esc(title)}</div><div class="row">{cells}</div></div>'
    sfx = "초" if lang == "kr" else " s"
    kA = kcard(t["kA"], "", [V["precA"], V["revA"], V["sent"], f"${V['costA']}", f"{V['latA']}{sfx}"])
    kB = kcard(t["kB"], " b", [V["precB"], V["revB"], "0%", "$0", f"{V['latB']}{sfx}"])
    spec_rows = "".join(f"<tr><td><b>{k}</b></td><td>{esc(r)}</td><td>{esc(where)}</td><td>{V['a' + k]}</td><td>{V['ms' + k]}{sfx}</td><td>{V['c' + k] if k in ('T3', 'T4') else '0'}</td></tr>"
                        for k, r, where in t["spec"])
    notes = "".join(f"<div><b>{esc(a)}</b>{b}</div>" for a, b in t["notes"])
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(t['title'])}</title><style>{CSS}</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script></head>
<body><div class="wrap"><h1>{esc(t['title'])}</h1><div class="sub">{esc(t['sub'])}</div>
<h2 class="s">{esc(t['s1'])}</h2>
<div class="top">{architecture(t)}<ol class="steps">{steps}</ol></div>
<div class="kpi">{kA}{kB}</div>
<h2 class="s">{esc(t['s2'])}</h2>
<div class="flows"><section class="flow"><h3>{esc(t['fA'])}</h3><pre class="mermaid">{mermaid(t, 'A')}</pre></section>
<section class="flow"><h3>{esc(t['fB'])}</h3><pre class="mermaid">{mermaid(t, 'B')}</pre></section></div>
<h2 class="s">{esc(t['s3'])}</h2>
<div class="det"><table><tr>{''.join(f'<th>{esc(x)}</th>' for x in t['spec_h'])}</tr>{spec_rows}</table><div class="notes">{notes}</div></div>
<div class="foot">Sources: ICDAR 2019 SROIE (CC-BY-4.0), WildReceipt, Tesseract 5.4, RapidOCR, Qwen2.5-VL via Ollama, Google Gemini API pricing 2026-10-31. github.com/minwoo-data/receipt-ocr-harness</div></div>
<script>mermaid.initialize({{startOnLoad:true, theme:'neutral', flowchart:{{curve:'basis', nodeSpacing:28, rankSpacing:36}}}});</script></body></html>"""

for lang, t in T.items():
    (ROOT / "docs" / f"workflow_{lang}.html").write_text(page(lang, t), encoding="utf-8")
print("wrote docs/workflow_en.html and docs/workflow_kr.html")
