# Plan: three offline analyses on the collected data (A, B, C)

Date: 2026-10-31. Owner: Minwoo Park. Deadline: poster PDF by Sunday 2026-11-01 23:59.
Scope: all three analyses replay data already in `results/`, `results_wild/`; **no new API calls**, each run under 5 minutes of CPU. The poster must still fit one 11 x 17 page.

## Why

The poster's central claim is that the **escalation signal, not the model, is the bottleneck**: a perfect router would send 27% of receipts to the cloud for 98.7% accuracy at $0.15 per 1,000, while the rule-based router sends 56% for 95.7%. A, B and C turn that claim from an observation into an analysis: can a learned signal close the gap (A), how does a time budget change the decision when the local reader is slow (B), and what exactly slipped past the code checks (C).

## A. Learned escalation signal

**Question.** How much of the oracle gap does a learned score close, using only signals available at inference time?

**Features (tier 1 only, no ground truth, no cloud output):** RapidOCR mean token confidence and low-confidence share; Tesseract mean confidence; line count; count of money tokens in the bottom half; rule reasons as indicators (total not found, several keyword amounts, keyword-less fallback, date not found, company not found); strong vs weak total keyword; both readers agree on total; both agree on date; absolute difference between the two readers' totals (capped); image aspect ratio.

**Label.** Tier-1 wrong on date or total (from `results/scores/rapidocr.jsonl`).

**Model.** Logistic regression (scikit-learn, standardized features, L2). Evaluation: 5-fold cross-validation on SROIE 300 (every prediction out of fold); then train on all of SROIE and test on WildReceipt 200 as a transfer check.

**Outputs.** `results/learned_router/coefficients.json`, `curve.json` (cloud share vs accepted precision as the score threshold sweeps), `summary.md`. Fig B gains one line: "learned router (out-of-fold)".

**Headline metrics.** (1) cloud share needed to match the rule router's 95.7%; (2) precision at the rule router's 56% cloud share; (3) AUC; (4) the same on Wild, trained on SROIE.

**Acceptance.** Report whichever way it goes. If the learned curve does not dominate the rule router out of fold, the poster says so (the honest version of "a learned signal is next").

**Risks.** Overfitting at n = 300 (mitigated by out-of-fold predictions only, no tuning on the test fold); feature leakage (features are computed from tier-1 records only; a unit test asserts no GT or cloud field is read).

## B. Latency-aware hedging

**Question.** When the local reader is slow, when should a receipt go to the cloud anyway?

**Policy.** Start the local VLM (tier 2). If its answer has not arrived by D seconds, fire the cloud call (Flash-Lite) as well; keep the first answer that passes the code checks; a flagged answer falls through to the next, then to review. Sweep D in {2, 5, 10, 20, 30, 60} seconds. Replay uses each receipt's recorded local and cloud latency and its recorded correctness.

**Metrics per D.** Cloud share (cost), accepted-answer precision, median and p90 user wait.

**Hardware sensitivity.** Local latency scaled by 1.0 (this laptop, Vulkan backend, 28 s median) and 0.25 (assumed CUDA-class GPU), labelled as an assumption.

**Outputs.** `results/hedge/curve.json`, `fig_hedge.png`, `summary.md`. Poster: one sentence in Results; README: the table. If the poster cannot fit it, README only.

**Risks.** Latencies were measured while other jobs ran on the same machine; stated in the caption.

## C. Leak taxonomy

**Question.** What did the code checks miss?

**Method.** For every receipt whose accepted answer was wrong (SROIE: local VLM 13, Flash-Lite 3, 3.6 Flash 2; Wild Flash-Lite 17), record predicted vs ground truth for date and total and classify by inspection of the OCR lines: picked another printed amount (cash tendered, subtotal, line item), digit misread, date order or format, breakdown internally consistent but wrong, ground truth questionable.

**Outputs.** `results/leaks.md` with one row per receipt and a count per class; README section; one clause on the poster if room ("most leaks are a different printed amount, not a misread").

**Risks.** Small counts; classification is by inspection and the rule is written down in the file.

## Order and time

| Step | Time | Done when |
|---|---|---|
| C leak taxonomy | 20 min | `results/leaks.md` with every leaked receipt classified |
| B hedging replay | 30 min | curve, figure, summary written; sanity: D = 0 equals all-cloud, D = infinity equals local-first |
| A learned router | 60 min | out-of-fold curve and Wild transfer written; leakage test passes |
| Poster update | 20 min | Fig B redrawn, Finding 2 sentence, Results line; all three columns still fit; PDF re-rendered |
| Commit and push | 5 min | repository updated |

Total about 2 h 15 min. Review by the author Saturday afternoon; submit Saturday night, keeping Sunday as buffer.
