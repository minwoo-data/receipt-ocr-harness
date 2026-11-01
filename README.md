# receipt-ocr-harness

**The model reads, the code re-checks.** A routing and verification harness for
receipt OCR, measured on 300 scanned receipts (ICDAR 2019 SROIE), 200 phone
photos (WildReceipt) and 43 synthetic adversarial receipts. Built for the
Heinz College Reverse Career Fair poster, Nov 4, 2026. Poster PDF:
`poster/Park_Minwoo_MISM_ReceiptOCR.pdf` (as submitted; its numbers are frozen in
`poster/printed_numbers.json`, and the numbers below were corrected after printing).

Walkthrough page (the poster's "How it works & code" QR): https://minwoo-data.github.io/receipt-ocr-harness/

Every number in the tables below is written by `scripts/22_readme.py` from
`src/harness/report_numbers.py`, the same source as the poster and the landing page.

## Question

A vision LLM reads receipts well but grades its own work badly: its
self-reported confidence is not evidence. When can a cheap local reader be
trusted, when should a receipt escalate, and how much of the model's error can
deterministic code catch without any ground truth?

## Correction after printing

<!-- gen:correction -->
**Corrected after printing, 2026-10-31.** The poster PDF is unchanged; the numbers below are the ones it printed that moved. Cause: `src/harness/normalize.py`, which turns printed text into dates and amounts, misread four-digit amounts without a thousands separator (`1039.00` as 103), decimal commas (`6,60` as 6.0), years written `Jul28'15`, and dates that were repeated or glued to a time. It parses both the WildReceipt answer key and T1's OCR text, so 15 labels on 14 WildReceipt receipts were wrong (`data/manifest/wild200_gt_corrections.jsonl`; the SROIE answer key had none) and T1 missed dates printed with the time attached. Two changes came with the fix: T1's self-signal and the learned features are recomputed with the current rules (`rules.refresh`), and in the policies with code checks T1's own date must pass the date check before T1 is accepted. That check changes no number on real receipts; before it, a synthetic receipt dated two years ahead that both OCR readers read the same way was auto-accepted at T1 without any check. Unchanged: the harness on scans, 96.9% correct, 4.3% review, 0.4 points below all-cloud.

| Number | Printed | Now |
|---|---|---|
| T1 alone (RapidOCR + rules), scans | 72.7% | 77.3% |
| Harness: accepted at T1, never left the machine, scans | 43.7% | 45.0% |
| Harness: sent to the cloud, scans | 56.3% | 55.0% |
| Harness: USD per 1,000, scans | 0.37 | 0.36 |
| Harness: cost below all-cloud, scans | 31% | 33% |
| Oracle router: sent to the cloud, scans | 27.3% | 22.7% |
| Router: sent to the cloud, scans | 56.3% | 55.0% |
| Local only: accepted answers correct, scans | 93.4% | 93.5% |
| Local only: sent to people, scans | 19.0% | 18.3% |
| Local only below the harness, scans (points) | 3.5 | 3.4 |
| T1 alone, photos | 55.0% | 63.0% |
| Local VLM alone, photos | 81.0% | 86.5% |
| Flash-Lite alone, photos | 86.5% | 93.5% |
| 3.6 Flash alone, photos | 86.5% | 93.5% |
| Harness: accepted answers correct, photos | 88.5% | 94.9% |
| Local only: accepted answers correct, photos | 89.1% | 93.4% |
| Local only: sent to people, photos | 31.5% | 32.0% |
| Learned hand-off score, AUC (scans, out of fold) | 0.89 | 0.84 |
| Learned score at the router's cloud share, scans | 95.7% | 94.7% |
<!-- /gen:correction -->

## Ladder of readers

<!-- gen:ladder -->
| Tier | Reader | Where | Date + total correct, SROIE 300 | Phone photos, Wild 200 | Median latency | USD per 1k |
|---|---|---|---|---|---|---|
| 1 | RapidOCR + rules (Tesseract as 2nd witness) | local CPU | 77.3% | 63.0% | 4.7 s | 0.00 |
| 2 | Qwen2.5-VL 3B via Ollama (Vulkan, RTX 2050 4 GB) | local GPU | 83.0% | 86.5% | 28 s | 0.00 |
| 3 | Gemini 3.1 Flash-Lite | cloud | 97.3% | 93.5% | 1.8 s | 0.54 |
| 4 | Gemini 3.6 Flash, thinking off | cloud | 98.0% | 93.5% | 1.9 s | 1.42 |
<!-- /gen:ladder -->

Exact match after normalization; company name is reported separately
(`results/scores/summary.md`) because it is a trade-name vs legal-name choice,
not a reading error.

## Routing policies (SROIE 300, tau = 0.9)

"Sent to cloud" counts every receipt whose image reached a cloud tier, including those that were then flagged and sent to review (`cloud_sent_share`; the share accepted from a cloud tier is `cloud_accepted_share`).

<!-- gen:routing -->
| Policy | Auto-accept | Review | Sent to cloud | Accepted answers correct | Wrong, auto-accepted per 1k | API USD per 1k | People USD per 1k | Total USD per 1k |
|---|---|---|---|---|---|---|---|---|
| All local (tier 1) | 100% | 0% | 0% | 77.3% | 227 | 0.00 | 0.00 | 0.00 |
| All cloud, cheap | 100% | 0% | 100% | 97.3% | 27 | 0.54 | 0.00 | 0.54 |
| All cloud, strong | 100% | 0% | 100% | 98.0% | 20 | 1.42 | 0.00 | 1.42 |
| Oracle router (escalates exactly the local misses) | 100% | 0% | 23% | 98.7% | 13 | 0.12 | 0.00 | 0.12 |
| Router: both OCR readers agree and confidence >= 0.9, else cloud | 100% | 0% | 55% | 95.7% | 43 | 0.29 | 0.00 | 0.29 |
| Harness: router + code checks, flagged answers escalate, then review | 95.7% | 4.3% | 55% | 96.9% | 30 | 0.36 | 14.43 | 14.80 |
| Harness with local VLM rung | 96.3% | 3.7% | 18% | 94.5% | 53 | 0.15 | 12.23 | 12.38 |
| Local only: T1, then local VLM with code checks, else review (no cloud) | 81.7% | 18.3% | 0% | 93.5% | 53 | 0.00 | 61.10 | 61.10 |

People's time is an assumption, not a measurement: 1 min to key the date and total of a reviewed receipt at $20/h, $0.33 per review (`REVIEW_MINUTES`, `REVIEW_WAGE_USD_H` in `src/harness/report_numbers.py`, or the environment variables `HARNESS_REVIEW_MINUTES`, `HARNESS_REVIEW_WAGE_USD_H`). API cost is measured. Once people are priced, all-cloud is the cheapest policy on scans: the harness saves $0.17 of API per 1,000 receipts and sends 4.3% of them to people, so it breaks even only if a review costs under $0.004 (0.7 s of a person's time at $20/h). The harness's case is where the images go (45% never leave the machine; local only keeps all of them, for $61.10 per 1,000 in people's time), not its price.
<!-- /gen:routing -->

Full tables, the tau sweep and per-receipt decisions: `results/harness/`,
`results_wild/harness/`.

## How sure are these numbers?

<!-- gen:uncertainty -->
One run, so the uncertainty measured here is which receipts happened to be sampled: 95% percentile bootstrap, 10,000 resamples of receipts, every policy replayed on the same resample so the differences are paired (`scripts/20_bootstrap.py`, `results*/harness/bootstrap.json`).

| Set | Harness: accepted correct | Local only | All cloud, cheap | All cloud minus harness, points | Harness minus local only, points |
|---|---|---|---|---|---|
| SROIE 300 | 96.9% (94.7–98.6%) | 93.5% (90.2–96.3%) | 97.3% (95.3–99.0%) | +0.4 (−1.9 to +2.9) | +3.4 (+1.2 to +5.9) |
| Wild 200 | 94.9% (91.3–98.1%) | 93.4% (88.9–97.1%) | 93.5% (90.0–96.5%) | −1.4 (−4.6 to +1.7) | +1.5 (−0.7 to +4.1) |

On scans the harness sends 55.0% (49–61%) to the cloud and 4.3% (2.3–6.7%) to people, at $0.36 (0.31–0.41) per 1,000. Reading: on scans the 0.4-point gap to all-cloud is inside the sampling noise (its interval spans zero), and the 3.4-point gap between the harness and local only is larger than the sampling noise. On photos neither gap is distinguishable from zero. The API saving holds across the interval: its upper end is below the all-cloud price.
<!-- /gen:uncertainty -->

## Code checks (verify.py): what they caught without an answer key

<!-- gen:checks -->
| Reader | Wrong date/total answers | Caught by code | Leaked | False flags |
|---|---|---|---|---|
| Local VLM (SROIE) | 51 | 38 (75%) | 13 | 49 |
| Flash-Lite (SROIE) | 8 | 5 (63%) | 3 | 15 |
| 3.6 Flash (SROIE) | 6 | 4 (67%) | 2 | 18 |
| Local VLM (Wild photos) | 27 | 20 (74%) | 7 | 51 |
| Flash-Lite (Wild photos) | 13 | 6 (46%) | 7 | 51 |
<!-- /gen:checks -->

Checks: sanitizer (NFKC normalization, EN/KO/JA/ZH injection patterns, field
whitelist, type and range), arithmetic identity (subtotal + tax + tip +
discount = total within 0.05, absent is not zero, tax-inclusive and
discount-netted variants), date plausibility within the dataset's era,
two-reader agreement (the LLM's total and date must appear in the independent
OCR text; abstains when the OCR saw no date). On phone photos the OCR witness
is weak, so agreement checks over-flag: the witness bounds the gate. T1's own
answer is accepted only when both OCR readers agree, OCR confidence is at least
0.9 and, in the policies with checks, its date passes the date check.

## Backstops for the errors that pass every check

<!-- gen:backstop -->
A leak is an auto-accepted answer that is wrong. In cloud mode on scans there are 9 in 300: 7 accepted at T1, where both OCR readers agreed on the same wrong answer, and 7 off by less than 0.10 (Malaysian 0.05 rounding), 6.47 misstated in all. Two backstops, replayed offline on the cached reads (`scripts/19_backstop.py`, `results*/backstop/summary.md`):

Random audit: a person re-keys a random share of auto-accepted receipts.

| Audit | Audited per 1k | Leaks caught per 1k (expected) | Share of leaks caught | P(finds at least one leak in this run of 300) | People USD per 1k |
|---|---|---|---|---|---|
| 2% | 20 | 0.6 | 2% | 18% | 6.67 |
| 5% | 47 | 1.5 | 5% | 37% | 15.57 |
| 10% | 97 | 3.0 | 10% | 62% | 32.23 |

Amount-ranked re-read: the top X% of auto-accepted receipts by accepted total (no answer key needed to rank) are re-read by T4; if T4's date or total differs, the receipt goes to a person.

| Top X% by total | Re-read by T4 | Leaks caught | Correct answers sent to people | Extra API USD per 1k | Extra people USD per 1k | Extra images to the cloud | Misstated amount covered |
|---|---|---|---|---|---|---|---|
| 5% | 14 | 0 of 9 | 0 | 0.07 | 0.00 | 2% | 0% |
| 10% | 29 | 0 of 9 | 0 | 0.14 | 0.00 | 4% | 0% |
| 20% | 57 | 0 of 9 | 0 | 0.27 | 0.00 | 8% | 0% |
| 30% | 86 | 3 of 9 | 0 | 0.41 | 3.33 | 13% | 1% |
| 100% | 286 | 7 of 9 | 1 | 1.35 | 8.90 | 45% | 79% |

Reading: an audit fixes only its own share of the leaks; its job is to measure the leak rate. Ranking by amount finds 0 of 9 in the top 20%: on scans the leaks sit on mid-sized receipts and are mostly cents. Re-reading every accepted receipt with T4 catches 7 of 9, but the API bill becomes $1.71 per 1,000, above sending every receipt to T4 ($1.42, 98.0% correct). On photos there are 8 leaks and the full re-read catches 5, with 3 correct answers sent to people. Card-statement matching, the other planned backstop, needs data this benchmark does not have.
<!-- /gen:backstop -->

## Hiding personal data before the cloud call (after the poster)

<!-- gen:pii -->
The idea: when the local reader fails, hide the personal data on the image on this machine, then let the cloud read it. Tested on the cloud-bound receipts (30 per dataset), each read by Flash-Lite twice: the original (U) and the masked image (M1); differences are M1 minus U on the same receipts, in points.

| Set | Masking | Refused before sending | Personal items hidden | Date + total read correctly, points (95% interval) | Sent to people, points | Verdict |
|---|---|---|---|---|---|---|
| Scans (SROIE) | label and pattern rules (r0) | 17% | 36% | 0.0 (0.0 to 0.0) | +13.3 | fails criterion 1, 4 |
| Scans (SROIE) | allowlist (rev1) | 0% | 100% | −16.7 (−30.0 to −3.3) | +93.3 | fails criterion 3, 4 |
| Photos (WildReceipt) | label and pattern rules (r0) | 13% | 15% | 0.0 (0.0 to 0.0) | +10.0 | fails criterion 1, 2, 4 |
| Photos (WildReceipt) | allowlist (rev1) | 7% | 93% | −14.3 (−28.6 to −3.6) | +63.3 | fails criterion 1, 2, 3, 4 |

**Field rules missed most names; hiding everything except dates and amounts cost about 15 points of accuracy and sent almost every receipt to people.** Names are often printed without a label word, and hiding the shop name makes the missing-field check flag every answer. Where receipts may not leave the company, local-only mode stays the answer; a local name detector would be the next step.

Read with care: labels are model-labeled (Gemini 3.1 Flash-Lite), so recall is relative to what it found; 30 receipts per dataset show only whether a large loss was seen; the rules were frozen and committed before any label (`results*/pii/r0/freeze.json`), and the allowlist run (rev1) is a disclosed revision after r0, for which the experiment's spending limit was raised once; known misses: names without a label word and values printed on the line below their label; reviewers of the plan saw sample text in rounds 1 and 4; whether the fill covered the date or total is not decidable on receipts whose date is printed with the time glued to it (the frozen locator does not find it), and no hand check was made. Per-receipt reads and replays: `results*/pii/`.
<!-- /gen:pii -->

## Adversarial set (43 synthetic receipts, `scripts/07_synth.py`)

Each model's answer checked directly (the routed system adds T1 in front; see the correction above for the date check on T1).

| Category | n | Model fooled (Lite / 3.6 / Qwen) | Expected gate fired (Lite) | Leaked |
|---|---|---|---|---|
| Date traps (future, 2009, 2-digit year, ambiguous) | 10 | 0 / 0 / 0 | 10 | 0 |
| Arithmetic traps | 11 | 1 / 0 / 1 | 11 | 0 |
| Injection, blatant (EN / KO / system prompt) | 6 | 0 / 0 / 0 | 6 | 0 |
| Injection, disguised (footer, fake JSON, assistant:, fullwidth) | 10 | 0 / 0 / 0 | 10 | 0 |
| Controls (clean, menu) | 6 | 0 / 2 / 2 | 6 | 0 |

Printed values and truth are stored separately in `data/synthetic/specs.json`.

## Targeted retry on the 20 flagged Flash-Lite receipts

| Mode | Fixed wrong to right | Broke right to wrong | Kept answer correct |
|---|---|---|---|
| Blind re-read (no previous values) | 0 | 1 | 15 / 20 |
| Guided re-read (previous values shown, no target) | 1 | 1 | 16 / 20 |

## Follow-up analyses (A-C plan: `docs/plan-abc.md`, triad-reviewed; D pre-registered by commit)

**A. Learned escalation signal** (`scripts/14_learned_router.py`, `src/harness/features.py`). Logistic regression on 14 tier-1 signals (OCR confidence, rule reasons, two-reader agreement, line counts), 5-fold out of fold on SROIE, then fit on SROIE and scored on Wild.

<!-- gen:learned -->
| Set | AUC | Rule router | Learned at the router's cloud share | Cloud share for the router's precision | Verdict |
|---|---|---|---|---|---|
| SROIE 300 (out of fold) | 0.842 | 55% cloud, 95.7% | 94.7% | 66% | no gain |
| Wild 200 (transfer) | 0.818 | 84% cloud, 94.0% | 93.5% | 76% | partial: fewer cloud calls, same precision |

The oracle gap (23% vs 55% cloud on SROIE) is not closed by these features; richer signals are needed.
<!-- /gen:learned -->

**B. Latency-aware hedging** (`hedge` policy in `04_harness.py`, `results/hedge/summary.md`). Start the local VLM; if it has not answered by D seconds, call Flash-Lite too; first answer that passes the checks wins; both flagged goes to review.

| local speed | D | cloud fired | accepted precision | review | USD / 1k | wait p50 |
|---|---|---|---|---|---|---|
| as measured (28 s) | 30 s | 43% | 96.3% | 19% | 0.23 | 28 s |
| as measured | 10 s | 100% | 98.6% | 5% | 0.54 | 12 s |
| 4x faster (assumed) | 10 s | 19% | 94.4% | 23% | 0.10 | 7 s |
| 4x faster | 5 s | 94% | 97.1% | 7% | 0.50 | 6.6 s |

**C. Leak taxonomy** (`scripts/12_leaks.py`, `results*/leaks/leaks.md`).
<!-- gen:leaks -->
Of 18 SROIE answers that were wrong yet passed every check, 16 were a different printed amount (cash tendered, subtotal, a line item), 1 a day/month swap, 1 both fields. On Wild (20 leaks) dates and amounts split: 12 date errors (3 day/month swaps), 8 other printed amounts.
<!-- /gen:leaks -->

**D. A gate built from the leaks, tested on a held-out set** (`verify.check_total_label`, `scripts/17_gate_experiment.py`, `results*/gate_total_label/comparison.md`). Two code checks written from the SROIE leaks only: `G_TOTAL_TENDER` (the model's total is printed only on payment lines: cash, change, accepted, card) and `G_TOTAL_ROUNDED` (the total is not a multiple of 0.05 while a total line prints the rounded amount within 2 cents). The gate was frozen at commit `07a5a7a` (verify.py sha256 `7b929ffe2419…`) before WildReceipt was run with it; both comparison files record that hash, and verify.py is still byte-identical. Opt-in (`04_harness.py --gates total_label`); the headline numbers above use the base gates. Re-scored on 2026-10-31 against the corrected WildReceipt labels.

<!-- gen:gate -->
| Set | Leaks caught, verdicts (receipts) | New false flags, verdicts (receipts) | Harness: accepted correct | Harness: review | Local only: accepted correct | Local only: review |
|---|---|---|---|---|---|---|
| SROIE 300 (dev, gate designed here) | 10 (9) | 0 (0) | 96.9% -> 97.2% | 4.3% -> 4.7% | 93.5% -> 95.4% | 18.3% -> 20.0% |
| Wild 200 (held-out) | 2 (1) | 3 (1) | 94.9% -> 95.5% | 21.5% -> 22.5% | 93.4% -> 94.0% | 32.0% -> 33.0% |
<!-- /gen:gate -->

Reading: a gate written from one dataset's failures transfers only partly. The SROIE leaks are Malaysian 0.05 rounding and cash tendered; the Wild leaks are mostly dates, and the false flag is a Tesseract artifact (`TOTAL: 65.398` read as 65.40). Ignoring three-decimal tokens is the obvious v2, but it was found on the held-out set, so it would need a fresh held-out set to be scored fairly. Leak analysis has to be redone per domain.

## Booth demo (local only)

`python scripts/21_demo.py` writes `demo/index.html` (git-ignored, because it
shows SROIE images): receipts picked by code, stepped through local-only mode
(T1 OCR and rules, local VLM, the four checks, the decision, then the answer
key), replayed from the cached local reads with the harness's own functions and
asserted equal to its decisions. No cloud call is made and no Gemini output is
read. `python scripts/21_demo.py --image receipt.jpg` reads a new receipt live
with RapidOCR and Tesseract and, if a local Ollama server is up, Qwen2.5-VL 3B.

## Reproduce

```
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
git config core.hooksPath .githooks
python scripts/01_fetch_sroie.py            # 300-receipt manifest (seed 20261031)
python scripts/11_fetch_wildreceipt.py      # 200-photo manifest (unambiguous dates only)
python scripts/07_synth.py                  # 43 adversarial receipts
python scripts/02_run_engine.py --engine rapidocr|tesseract|qwen|gemini-lite|gemini [--manifest ... --out ...]
python scripts/05_retry.py; python scripts/08_synth_eval.py --engine gemini-lite
python scripts/run_all.py                   # offline: scores, harness, gate D, leaks, learned signal,
                                            # backstops, bootstrap, charts, pages, README blocks, demo
```

`run_all.py` makes no API call and does not re-render the submitted poster
(pass `--poster` to do that); it ends by checking that the poster PDF still
matches the hash in `poster/printed_numbers.json`.

Keys: `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` from the environment or
`~/.config/boda/config.json`. No key file exists inside this repository; a
pre-commit hook blocks key-shaped strings; a local spend cap
(`HARNESS_SPEND_CAP_USD`, default 5) stops paid calls. Total API spend for
every run in this repository: about $1.

## Data and attribution

Per-receipt outputs under `results*/` are derived from SROIE (CC-BY-4.0) and WildReceipt (research use) and follow those datasets' licenses; dataset images are not redistributed here. The MIT license covers the code.

- ICDAR 2019 SROIE (Huang et al., arXiv:2103.10213), `jsdnrs/ICDAR2019-SROIE`
  mirror, CC-BY-4.0. Images downloaded by script, not committed.
- WildReceipt (Sun et al., arXiv:2103.14470), OpenMMLab distribution. Research
  use; images not committed.
- `src/harness/vendor_boda/` is adapted from the author's
  [boda](https://github.com/minwoo-data/boda) project (see NOTICE).
- Gemini prices from the official pricing page, 2026-10-31
  (`results/pricing_sources.md`).

## License

MIT.
