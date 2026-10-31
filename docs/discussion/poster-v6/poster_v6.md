# Poster v6.3 text (for review)

Context: 11 x 17 in landscape poster, Heinz College Reverse Career Fair (2026-11-04). Readers: recruiters and hiring managers for ML/AI engineer roles, walking past; goal is a 30-second read. Two figures are images (described in captions). QR 1 = portfolio, QR 2 = walkthrough page.

Review question: what message does this poster give in 30 seconds, is it the intended one (LLM output is trusted only through code checks; local first, cloud when checks fail, people last; local-only mode when data cannot leave), and what is unclear, redundant or missing?

## Header

LLM reads, code verifies
Can you trust what an LLM reads? When should it call the cloud? What if the data can't leave?
Minwoo Park · MISM, Business Intelligence & Data Analytics (AI Management) · Carnegie Mellon University
Portfolio & resume
How it works & code

## Column 1

From production
90%+ less reconciliation time · sole engineer · 729 PRs
7 LLMs benchmarked on a hand-built 90-receipt, 8-currency set
87 s → 10 s worst-case latency with Gemini → Claude failover
Rolled back confidence-based auto-approval: why this harness exists
1Can you trust what an LLM reads?

Not its confidence. Check every answer with code.

Four checks on every model answer (no answer key, no model confidence)
Sanitizer: injection patterns in EN/KO/JA/ZH, field whitelist
Arithmetic: subtotal + tax + tip + discount = total
Date plausibility: a real date in the receipts' era
Two-reader: the total and date must appear in the OCR text
Zero flags → auto-accept. Flagged → escalate one rung → still flagged → human review.
With no answer key, the checks caught
38 of 51
wrong answers from the local model
5 of 8
wrong answers from the cloud model
Adversarial set (cloud, cheap)	n	model fooled	gate fired	leaked
Date traps	10	0	10	0
Arithmetic traps	11	1	11	0
Injection, blatant	6	0	6	0
Injection, disguised	10	0	10	0
Controls	6	0	6	0

## Column 2

2When should it call the cloud?

Local first, cloud when the checks fail, people last.

On this machine
Cloud
T1 · OCR + rules
RapidOCR + Tesseract · CPU · $0
T2 · local VLM
Qwen2.5-VL 3B · 4 GB GPU · $0
T3 · cloud, cheap
Gemini 3.1 Flash-Lite · $0.54 per 1k
T4 · cloud, strong
Gemini 3.6 Flash · $1.42 per 1k
Claude failover
Each reader alone	scans: date + total	phone photos	median
Local OCR + rules	72.7%	55.0%	4.7 s
Local VLM 3B	83.0%	81.0%	28.3 s
Cloud, cheap	97.3%	86.5%	1.8 s
Cloud, strong	98.0%	86.5%	1.9 s
Fig A. Where 300 scans end up under each policy, accepted-answer accuracy and USD per 1,000.

The harness: 96.9% correct with 56% of receipts sent to the cloud and 4.3% to people, $0.37 per 1,000 (all cloud: 97.3%, $0.54). The strong model adds 0.7 points for 2.7× the price: escalate to people, not to a bigger model.

## Column 3

Fig B. Share of receipts sent to the cloud vs accuracy as the hand-off threshold moves; ★ = a router that knew the answers.

A router that knew the answers would send only 27% to the cloud for 98.7%; the simple rules send 56% for 95.7%. The hard part is knowing when to call the cloud, not the model. A learned “call the cloud?” score (14 features, out-of-fold AUC 0.89) did no better, so the two simple rules stayed.

3What if the data can't leave?

Run local-only: same checks, more human review.

	Cloud harness	Local only
Scans: correct	96.9%	93.4%
Scans: to people	4.3%	19.0%
Scans: USD per 1k	$0.37	$0
Photos: correct	88.5%	89.1%
Photos: to people	21.5%	31.5%

Photos: same accuracy, more review; scans: 3.4 points lower. Keeping data in costs mostly people's time. In cloud mode only step 4 sends the image out; checks and routing stay local.

Check rules are domain assets: one built from scan errors caught 10 of 16 there, but 1 receipt on held-out photos, with 1 false alarm.

Next: 10k receipts; invoices and statements; layout features for the hand-off decision; a weekly drift metric.

## Footer

300 scanned receipts (ICDAR 2019 SROIE) · 200 phone photos (WildReceipt) · 43 synthetic adversarial receipts. Date and total must match exactly; scoring is code, never a model.
Run of 2026-10-31 · code and every result in the repository
Sources. ICDAR 2019 SROIE (Huang et al., arXiv:2103.10213), CC-BY-4.0 · WildReceipt (Sun et al., arXiv:2103.14470) · Tesseract 5.4, RapidOCR / PP-OCR, Qwen2.5-VL (Apache 2.0) via Ollama · Google Gemini API pricing page, 2026-10-31 · Fallback chain and sanitizer adapted from the author's open-source boda (MIT). Production figures are from the author's 2026 engagement; the platform is private.
