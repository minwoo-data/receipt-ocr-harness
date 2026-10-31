# Poster content (11 x 17 in, landscape) - draft v1, 2026-10-31

Word budget: 350. Fonts: Arial. No drop shadows, no 3D, no transparent text boxes.
Margins on all sides. QR code required (minwoopark.dev). Sources listed.
Numbers in [brackets] are filled from results/ once the runs complete.

## Header
**LLM reads, code verifies**
A routing and verification harness for receipt OCR
Minwoo Park | MISM, Business Intelligence & Data Analytics (AI Management) | Heinz College
github.com/minwoo-data/receipt-ocr-harness | minwoopark.dev  [QR]

## 1. Problem & scope
- Built the receipt-OCR side of a production expense platform (20 employees, 10 corporate cards,
  ~200 receipts/month) that cut reconciliation time 90%+; sole engineer, 729 merged PRs.
- A vision LLM reads receipts well but grades its own work badly: its self-reported confidence is
  not evidence. In production an auto-approval path built on that score was rolled back.
- Question: when is a cheap local reader enough, when should a receipt escalate, and how much of the
  model's error can deterministic code catch with no ground truth?

## 2. System (diagram)
Intake -> Tier 1 local OCR + rules (RapidOCR / Tesseract) -> Tier 2 local VLM (Qwen2.5-VL 3B, Ollama)
-> Tier 3 cloud, cheap (Gemini 3.1 Flash-Lite) -> Tier 4 cloud, strong (Gemini 3.6 Flash)
Every VLM answer passes code checks before it can be auto-accepted:
sanitizer (NFKC normalization, multilingual injection patterns, field whitelist, type/range)
| arithmetic identity subtotal + tax + tip + discount = total, absent is not zero
| date plausibility | two-reader agreement (LLM total and date must appear in the OCR text)
| targeted retry, one attempt, on the flagged field only | route: accept / escalate / human review.

Production evidence (verified): 90-receipt, 8-currency golden set built by hand; 7 LLMs benchmarked;
Gemini-to-Claude fallback chain with fast-fail budget after a 503 storm took one receipt from 87 s
to ~10 s worst case; +11% amount-extraction pass rate from fixing a validator that silently dropped
12 model-returned fields; 40-receipt prompt experiment: production prompt 39/40, rewrites did not beat it.

## 3. Experiment
- 300 public receipts (ICDAR 2019 SROIE, CC-BY-4.0), seed-fixed sample; exact match on company,
  date, total after normalization; scoring is code, never a model.
- 43 synthetic adversarial receipts (future / ancient dates, arithmetic traps, prompt injection in
  English and Korean, disguised footers, fullwidth text, non-receipt controls). Printed values and
  truth are stored separately so a generator slip cannot contaminate a label.
- Gates are tuned on the natural set only; the synthetic set is held out for evaluation.

## 4. Results (figures)
- Fig A: where receipts end up by policy (local / local VLM / cloud cheap / cloud strong / review)
  with accepted-answer precision and cost per 1k.
- Fig B: escalation curve, cloud share vs accepted precision, router vs harness, oracle ceiling.
- Fig C: waterfall per VLM tier: model errors -> caught by code -> leaked.
- Table: tiers: date+total accuracy, median latency, USD per 1k. [fill]
- Table: adversarial set: fooled / caught / leaked by category. [fill]
- Table: targeted retry: blind vs guided, fixed / broke / kept. [fill]

## 5. Findings (3 lines, numbers from results) [fill]
- Local OCR + rules reaches [x]% on date+total; a local 3B VLM [y]%; cloud Flash-Lite [z]%.
- With code gates, auto-accepted answers are [p]% correct at [c]% cloud share and $[k] per 1k;
  the gap to the oracle router is [g] points.
- Code caught [a] of [b] model errors on the natural set and [m] of [n] adversarial traps;
  the model itself was fooled by [i] of [j] injections. Blind retry fixed [f1], guided [f2],
  guided broke [b2] right answers (anchoring).

## 6. Next
10k receipts (SROIE + CORD + WildReceipt + augmentation), per-currency tolerances, a learned
escalation signal to close the oracle gap, drift monitoring tied to a monthly spend cap.

## Sources
ICDAR 2019 SROIE (Huang et al., arXiv:2103.10213), jsdnrs mirror, CC-BY-4.0 | Tesseract 5.4 (Apache 2.0)
| RapidOCR / PP-OCR (Apache 2.0) | Qwen2.5-VL (Apache 2.0) via Ollama | Google Gemini API pricing page
(2026-10-31) | Author's boda project (MIT) for the fallback chain and sanitizer.
