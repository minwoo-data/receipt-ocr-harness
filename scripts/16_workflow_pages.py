"""16_workflow_pages.py - docs/workflow_en.html and docs/workflow_kr.html:
process-mining style flowcharts (Mermaid) with decision diamonds, edge
percentages from the SROIE 300 run, model names, escalation criteria and the
vendor fallback. Two lanes: cloud available / local only.
    python scripts/16_workflow_pages.py
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

T = {
 "en": dict(title="Receipt OCR harness: how one receipt is processed", sub="Edge labels = share of the 300 SROIE scans that took that path (run of 2026-10-31). Model self-confidence is never used to approve.",
   laneA="A. Cloud available: accepted answers 96.9% correct, 4.3% to people, 52% of receipts touch the cloud, $0.37 per 1k, median 6 s",
   laneB="B. Local only (no data leaves the machine): accepted answers 93.4% correct, 19% to people, $0, median 27 s",
   intake="Receipt image", t1="T1 local OCR + rules<br/>RapidOCR text + Tesseract witness<br/>rules: vendor / date / total<br/>alone: 72.7%, 4.7 s, $0",
   sig="T1 self-signal<br/>both readers agree on date and total<br/>AND OCR confidence >= 0.9?", accept="AUTO-ACCEPT", review="HUMAN REVIEW",
   t3="T3 Gemini 3.1 Flash-Lite<br/>same prompt + JSON schema<br/>alone: 97.3%, 1.8 s, $0.54 per 1k", t4="T4 Gemini 3.6 Flash, thinking off<br/>alone: 98.0%, 1.9 s, $1.42 per 1k",
   t2="T2 local VLM Qwen2.5-VL 3B (Ollama)<br/>same prompt + JSON schema<br/>alone: 83.0%, 28 s on RTX 2050, $0",
   gates="Code checks (no answer key)<br/>1 sanitizer: NFKC, EN/KO/JA/ZH injection patterns, whitelist, types<br/>2 arithmetic: subtotal+tax+tip+discount = total (0.05, absent is not 0)<br/>3 date plausible<br/>4 two-reader: model total and date appear in OCR text",
   zero="0 flags", flagged="1+ flags", yes="yes", no="no",
   fb="Vendor fallback<br/>Gemini 429/503 -> 1 fast-fail attempt -> Claude Haiku<br/>circuit breaker opens after 3 failures, 60 s cooldown",
   note="Reading the numbers: in lane A, 43.7% are accepted at T1, 51.7% at T3, 0.3% at T4, 4.3% go to people. Code checks caught 5 of Flash-Lite's 8 wrong answers and 38 of the local model's 51. The oracle (knows the answers) would send only 27% to the cloud for 98.7%: the escalation signal, not the model, is the bottleneck."),
 "kr": dict(title="영수증 OCR 하네스: 영수증 한 장의 처리 흐름", sub="화살표 숫자 = SROIE 스캔 300장 중 그 길을 지난 비율(2026-10-31 실행). 모델의 self-reported confidence 는 어디서도 승인에 쓰지 않습니다.",
   laneA="A. 클라우드 가능: 자동승인 정확도 96.9%, 사람 검토 4.3%, 클라우드 호출 52%, $0.37 / 1k, 중앙 6초",
   laneB="B. 로컬 전용(데이터 반출 없음): 자동승인 정확도 93.4%, 사람 검토 19%, $0, 중앙 27초",
   intake="영수증 이미지", t1="T1 로컬 OCR + 규칙<br/>RapidOCR 텍스트 + Tesseract 증인<br/>규칙으로 vendor / date / total<br/>단독 72.7%, 4.7초, $0",
   sig="T1 자기 신호<br/>두 OCR 의 날짜·총액 일치<br/>AND OCR confidence >= 0.9?", accept="자동승인", review="사람 검토",
   t3="T3 Gemini 3.1 Flash-Lite<br/>같은 prompt + JSON schema<br/>단독 97.3%, 1.8초, $0.54 / 1k", t4="T4 Gemini 3.6 Flash, thinking off<br/>단독 98.0%, 1.9초, $1.42 / 1k",
   t2="T2 로컬 VLM Qwen2.5-VL 3B (Ollama)<br/>같은 prompt + JSON schema<br/>단독 83.0%, RTX 2050 에서 28초, $0",
   gates="코드 검증 (정답 없이)<br/>1 sanitizer: NFKC, EN/KO/JA/ZH injection 패턴, 화이트리스트, 타입<br/>2 arithmetic: subtotal+tax+tip+discount = total (0.05, 결측은 0 아님)<br/>3 날짜 타당성<br/>4 two-reader: 모델의 총액·날짜가 OCR 텍스트에 있는가",
   zero="플래그 0개", flagged="플래그 1개 이상", yes="예", no="아니오",
   fb="Vendor fallback<br/>Gemini 429/503 -> fast-fail 1회 -> Claude Haiku<br/>연속 3회 실패 시 circuit breaker 60초",
   note="읽는 법: A 레인에서 43.7%는 T1 에서, 51.7%는 T3 에서, 0.3%는 T4 에서 자동승인되고 4.3%가 사람에게 갑니다. 코드 검증은 Flash-Lite 오류 8건 중 5건, 로컬 VLM 오류 51건 중 38건을 잡았습니다. 정답을 아는 오라클은 27%만 클라우드로 보내고 98.7%: 병목은 모델이 아니라 승격 신호입니다."),
}

def mermaid(t, lane):
    if lane == "A":
        return f"""flowchart LR
  IN([{t['intake']}]) --> T1[{t['t1']}]
  T1 --> SIG{{{t['sig']}}}
  SIG -- {t['yes']} 43.7% --> ACC1([{t['accept']}])
  SIG -- {t['no']} 56.3% --> T3[{t['t3']}]
  T3 -. 429 / 503 .-> FB[{t['fb']}]
  FB -.-> G3
  T3 --> G3{{{t['gates']}}}
  G3 -- {t['zero']} 51.7% --> ACC2([{t['accept']}])
  G3 -- {t['flagged']} 4.6% --> T4[{t['t4']}]
  T4 --> G4{{{t['gates']}}}
  G4 -- {t['zero']} 0.3% --> ACC3([{t['accept']}])
  G4 -- {t['flagged']} 4.3% --> REV([{t['review']}])
  classDef t1 fill:#dce9fa,stroke:#2a78d6; classDef t3 fill:#d9f3e9,stroke:#1baf7a; classDef t4 fill:#fbefcf,stroke:#eda100;
  classDef acc fill:#e3f6e3,stroke:#0ca30c; classDef rev fill:#fae0e0,stroke:#d03b3b; classDef fb fill:#f3f2ee,stroke:#898781;
  class T1 t1; class T3 t3; class T4 t4; class ACC1,ACC2,ACC3 acc; class REV rev; class FB fb;"""
    return f"""flowchart LR
  IN([{t['intake']}]) --> T1[{t['t1']}]
  T1 --> SIG{{{t['sig']}}}
  SIG -- {t['yes']} 43.7% --> ACC1([{t['accept']}])
  SIG -- {t['no']} 56.3% --> T2[{t['t2']}]
  T2 --> G2{{{t['gates']}}}
  G2 -- {t['zero']} 37.3% --> ACC2([{t['accept']}])
  G2 -- {t['flagged']} 19.0% --> REV([{t['review']}])
  classDef t1 fill:#dce9fa,stroke:#2a78d6; classDef t2 fill:#fde3d6,stroke:#eb6834;
  classDef acc fill:#e3f6e3,stroke:#0ca30c; classDef rev fill:#fae0e0,stroke:#d03b3b;
  class T1 t1; class T2 t2; class ACC1,ACC2 acc; class REV rev;"""

for lang, t in T.items():
    html = f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t['title']}</title>
<style>body{{margin:0;background:#fff;color:#0b0b0b;font-family:Arial,"Malgun Gothic",sans-serif;line-height:1.4}} .wrap{{max-width:1700px;margin:0 auto;padding:16px 22px}}
h1{{font-size:24px;margin:0 0 4px}} .sub{{color:#52514e;font-size:14px;margin-bottom:10px}} h2{{font-size:16px;margin:14px 0 6px}}
.lane{{border:1.5px solid #e1e0d9;border-radius:12px;padding:8px 12px;margin-bottom:12px}} .mermaid{{font-size:13px}} .note{{font-size:13px;color:#52514e;margin-top:8px}}</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script></head>
<body><div class="wrap"><h1>{t['title']}</h1><div class="sub">{t['sub']}</div>
<section class="lane"><h2>{t['laneA']}</h2><pre class="mermaid">{mermaid(t, 'A')}</pre></section>
<section class="lane"><h2>{t['laneB']}</h2><pre class="mermaid">{mermaid(t, 'B')}</pre></section>
<div class="note">{t['note']}</div>
<div class="note">Sources: ICDAR 2019 SROIE (CC-BY-4.0), WildReceipt, Tesseract 5.4, RapidOCR, Qwen2.5-VL via Ollama, Google Gemini API pricing 2026-10-31. github.com/minwoo-data/receipt-ocr-harness</div></div>
<script>mermaid.initialize({{startOnLoad:true, theme:'neutral', flowchart:{{curve:'basis', nodeSpacing:30, rankSpacing:40}}}});</script></body></html>"""
    (ROOT / "docs" / f"workflow_{lang}.html").write_text(html, encoding="utf-8")
print("wrote docs/workflow_en.html and docs/workflow_kr.html")
