# Pricing sources (USD per 1M tokens, paid tier)

Checked 2026-10-31. Cost per receipt in `results/` is computed from the
provider's reported token usage times these rates. Local tiers cost $0.00 in
API fees; their CPU/GPU time is reported as latency instead.

| Model | Input | Output | Source | Note |
|---|---|---|---|---|
| gemini-3.8-flash | 0.75 | 3.75 | ai.google.dev/gemini-api/docs/pricing | Rate through 2026-12-31; 1.50 / 7.50 from 2027-01-01. Output price includes thinking tokens, so thinking is forced to minimal. |
| gemini-3.1-flash-lite | 0.25 | 1.50 | ai.google.dev/gemini-api/docs/pricing | Text/image input. |
| claude-haiku-5-5 | 0.10 | 0.50 | Anthropic model table (claude-api skill, cached 2026-10-06) | Prompts up to 100K tokens. |
| qwen3-vl:2b (Ollama) | 0 | 0 | local | RTX 2050 GPU runner crashed (driver 545 / CUDA 12.3 vs Ollama 0.40 CUDA build); measured on CPU. |
| RapidOCR, Tesseract 5.4 | 0 | 0 | local | CPU only. |

Production context (not re-measured here): the April 2026 Accuver benchmark
ran on gemini-2.5-flash, which the Gemini API retired for new users before
this experiment (404 on 2026-10-31), so the cloud tier here is the current
Flash generation.
