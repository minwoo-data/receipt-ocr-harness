# receipt-ocr-harness

**The model reads, the code re-checks.** A routing and verification harness for
receipt OCR, measured on 300 scanned receipts (ICDAR 2019 SROIE), 200 phone
photos (WildReceipt) and 43 synthetic adversarial receipts. Built for the
Heinz College Reverse Career Fair poster, Nov 4, 2026. Poster PDF:
`poster/Park_Minwoo_MISM_ReceiptOCR.pdf`.

## Question

A vision LLM reads receipts well but grades its own work badly: its
self-reported confidence is not evidence. When can a cheap local reader be
trusted, when should a receipt escalate, and how much of the model's error can
deterministic code catch without any ground truth?

## Ladder of readers

| Tier | Reader | Where | Date + total correct, SROIE 300 | Phone photos, Wild 200 | Median latency | USD per 1k |
|---|---|---|---|---|---|---|
| 1 | RapidOCR + rules (Tesseract as 2nd witness) | local CPU | 72.7% | 55.0% | 4.7 s | 0 |
| 2 | Qwen2.5-VL 3B via Ollama (Vulkan, RTX 2050 4 GB) | local GPU | 83.0% | 81.0% | 28 s | 0 |
| 3 | Gemini 3.1 Flash-Lite | cloud | 97.3% | 86.5% | 1.8 s | 0.54 |
| 4 | Gemini 3.6 Flash, thinking off | cloud | 98.0% | 86.5% | 1.9 s | 1.42 |

Exact match after normalization; company name is reported separately
(`results/scores/summary.md`) because it is a trade-name vs legal-name choice,
not a reading error.

## Routing policies (SROIE 300, tau = 0.9)

| Policy | Auto-accept | Review | Cloud share | Accepted answers correct | USD per 1k |
|---|---|---|---|---|---|
| All local (tier 1) | 100% | 0% | 0% | 72.7% | 0.00 |
| All cloud, cheap | 100% | 0% | 100% | 97.3% | 0.54 |
| All cloud, strong | 100% | 0% | 100% | 98.0% | 1.42 |
| Oracle router (escalates exactly the local misses) | 100% | 0% | 27% | 98.7% | 0.15 |
| Router: both OCR readers agree and confidence >= 0.9, else cloud | 100% | 0% | 56% | 95.7% | 0.30 |
| Harness: router + code checks, flagged answers escalate, then review | 95.7% | 4.3% | 52% | 96.9% | 0.37 |
| Harness with local VLM rung | 96.3% | 3.7% | 15% | 94.5% | 0.16 |

Full tables, the tau sweep and per-receipt decisions: `results/harness/`,
`results_wild/harness/`.

## Code checks (verify.py): what they caught without an answer key

| Reader | Wrong date/total answers | Caught by code | Leaked | False flags |
|---|---|---|---|---|
| Local VLM (SROIE) | 51 | 38 (75%) | 13 | 49 |
| Flash-Lite (SROIE) | 8 | 5 (63%) | 3 | 15 |
| 3.6 Flash (SROIE) | 6 | 4 (67%) | 2 | 18 |
| Flash-Lite (Wild photos) | 27 | 10 (37%) | 17 | 47 |

Checks: sanitizer (NFKC normalization, EN/KO/JA/ZH injection patterns, field
whitelist, type and range), arithmetic identity (subtotal + tax + tip +
discount = total within 0.05, absent is not zero, tax-inclusive and
discount-netted variants), date plausibility within the dataset's era,
two-reader agreement (the LLM's total and date must appear in the independent
OCR text; abstains when the OCR saw no date). On phone photos the OCR witness
is weak, so agreement checks over-flag: the witness bounds the gate.

## Adversarial set (43 synthetic receipts, `scripts/07_synth.py`)

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

## Reproduce

```
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
git config core.hooksPath .githooks
python scripts/01_fetch_sroie.py            # 300-receipt manifest (seed 20261031)
python scripts/11_fetch_wildreceipt.py      # 200-photo manifest (unambiguous dates only)
python scripts/07_synth.py                  # 43 adversarial receipts
python scripts/02_run_engine.py --engine rapidocr|tesseract|qwen|gemini-lite|gemini [--manifest ... --out ...]
python scripts/03_score.py; python scripts/04_harness.py; python scripts/05_retry.py
python scripts/08_synth_eval.py --engine gemini-lite; python scripts/06_charts.py
python scripts/10_fill_poster.py; python scripts/09_render_poster.py
```

Keys: `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` from the environment or
`~/.config/boda/config.json`. No key file exists inside this repository; a
pre-commit hook blocks key-shaped strings; a local spend cap
(`HARNESS_SPEND_CAP_USD`, default 5) stops paid calls. Total API spend for
every run in this repository: about $1.

## Data and attribution

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
