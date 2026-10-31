# receipt-ocr-harness

**The model reads, the code re-checks.** A verification and routing harness for
receipt OCR, measured on 300 public receipts plus a synthetic adversarial set.

Status: experiment in progress (Oct 31 - Nov 1, 2026). Results land in
`results/` and are summarized here when the run completes.

## Question

A vision LLM reads receipts well, but it grades its own work badly: its
self-reported confidence is not evidence. When can a cheap local reader be
trusted, when should a receipt escalate to a stronger model, and how much of
the model's error can deterministic code catch without any ground truth?

## Ladder

| Tier | Reader | Where | Output |
|---|---|---|---|
| 1 | RapidOCR / Tesseract + rules | local CPU | text + per-token confidence |
| 2 | Qwen3-VL 2B (Ollama) | local GPU | structured JSON, same schema as tier 3 |
| 3 | Gemini 2.5 Flash, Claude failover | cloud | structured JSON |

## Harness (code, not model, decides)

1. Output sanitizer: NFKC normalization, multilingual injection patterns,
   field whitelist, type and range checks.
2. Arithmetic identity: subtotal + tax + tip + discount = total within 0.02,
   absent fields are not zero.
3. Date plausibility: parseable, not in the future, not ancient.
4. Two-reader agreement: the LLM's total and date must appear in the
   independent OCR text.
5. Targeted retry (one attempt) on the flagged field only, blind vs guided.
6. Routing: auto-accept only when every check passes; otherwise escalate or
   send to human review. Model confidence is logged, never used to approve.

## Reproduce

```
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
git config core.hooksPath .githooks
python scripts/01_fetch_sroie.py
```

Keys: `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` from the environment or
`~/.config/boda/config.json`. No key file exists inside this repository.

## Data and attribution

- ICDAR 2019 SROIE (Huang et al.), via the `jsdnrs/ICDAR2019-SROIE` mirror on
  Hugging Face, CC-BY-4.0. Images are downloaded by script and not committed.
- `src/harness/vendor_boda/` is adapted from the author's
  [boda](https://github.com/minwoo-data/boda) project (see NOTICE).

## License

MIT.
