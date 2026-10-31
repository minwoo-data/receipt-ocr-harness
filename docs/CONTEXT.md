# Working context (read this first when resuming)

Updated 2026-10-31 11:40 ET. Owner: Minwoo Park. Assistant session: Claude Code, hub item wi-261031-5969.

## Goal and deadline
Heinz Reverse Career Fair poster (event Wed 2026-11-04). **PDF upload deadline Sun 2026-11-01 23:59** at https://forms.gle/Q5efpF1Y71cDPNcu8, file `poster/Park_Minwoo_MISM_ReceiptOCR.pdf`, 11 x 17 in, Arial, QR present. The user uploads the form personally (Google login).

## What exists (all committed, repo private: github.com/minwoo-data/receipt-ocr-harness)
- Data: SROIE 300 (`data/manifest/sroie300.jsonl`, images local only), WildReceipt 200 (`wild200.jsonl`, day_first=false), synthetic 43 (`data/synthetic/`).
- Engine outputs: `results/{rapidocr,tesseract,qwen,gemini-lite,gemini}`, `results_wild/...`, `results/synth/...` all complete (Wild qwen 199/200).
- Analysis: `results/scores/`, `results/harness/{policies,tau_sweep,waterfall,per_receipt}`, `results_wild/harness/`, `results/synth/eval_*.md`, `results/retry/gemini-lite_summary.md`.
- Poster v2 fitted: `poster/poster.template.html` (edit this) + `poster/findings.json` -> `10_fill_poster.py` -> `09_render_poster.py`. Preview `poster/preview.png`.
- README has the full result tables. Spend ledger `results/spend_ledger.json` (about $1; cap $5).
- Plan for the three extra analyses: `docs/plan-abc.md` (v2, triad-reviewed; round records in `docs/discussion/plan-abc/`).

## Decisions already made (do not reopen)
- Tiers: T1 RapidOCR+rules (Tesseract witness), T2 qwen2.5vl:3b via Ollama on Vulkan (`CUDA_VISIBLE_DEVICES=-1 ollama serve`; CUDA runner crashes on driver 545), T3 gemini-3.1-flash-lite, T4 gemini-3.6-flash (2.5-flash retired for new users; 3.8-flash 503/504).
- Keys only from env or `~/.config/boda/config.json`; never read or print key values. Gemini key is paid tier (jkjk08021@ account). Anthropic key: user will add later; Claude failover stays in the poster as design + production evidence.
- Company field compared space-insensitively; arithmetic tolerance 0.05; date window = dataset era; two-reader date check abstains when OCR saw no date.
- boda README `sk-ant-` string is a placeholder (checked by shape); no key leaks in either repo.
- Memory pressure: run at most one heavy local process at a time; Claude Code kills background jobs when RAM is low and they must be restarted only on the user's word (user has given a standing "restart and continue").

## Remaining steps, in order (user approved: do them in this session, to the end)
1. Triad round 2: architect PASS, end-user PASS, LLM lens pending -> write `docs/discussion/plan-abc/round-2.md` + `CONSENSUS.md`; apply the small edits (table order B -> C -> A, Wild baselines in Why, dataset intro, params dict, schema file, run_all.py).
2. **B hedge**: `decide(row, policy, params)` in `scripts/04_harness.py`; policy `hedge` per plan §B; sweep D x scale; write `<root>/hedge/`; two pytest sanity tests; `06_charts.py` adds `fig_hedge.png`.
3. **C leaks**: `scripts/12_leaks.py` -> `<root>/leaks/leaks.jsonl` + `leaks.md`, classes by code (plan §C).
4. **A learned router**: `src/harness/features.py` + `scripts/14_learned_router.py` (scikit-learn; pip install needed), out-of-fold on SROIE, transfer to Wild; `06_charts.py` adds the learned line to Fig B.
5. `scripts/run_all.py` runs 04 -> 12 -> 14 -> 06 for both roots, then 10 -> 09.
6. Poster: Finding 2 sentence with A's result, Results line for B if it fits, re-render, check all three `.col` scrollHeights <= 794 px.
7. README: sections for A, B, C. Commit, push. Flip repo public: `gh repo edit minwoo-data/receipt-ocr-harness --visibility public --accept-visibility-change-consequences`.
8. Tell the user the PDF path; user uploads; then `hub done`.

## Key numbers (run of 2026-10-31, SROIE 300, date+total exact)
T1 72.7% / T2 83.0% (28 s) / T3 97.3% ($0.54 per 1k) / T4 98.0% ($1.42). Oracle 27% cloud -> 98.7% ($0.15). Router 56% -> 95.7%. Harness 96.9% at 4.3% review. Gates: T2 51 errors 38 caught, T3 8/5, T4 6/4. Wild: T1 55%, T2 81%, T3 86.5%, oracle 90%, router 84% cloud -> 87.0%. Synthetic: 16 injections, 0 fooled, 0 leaked. Retry: blind 0 fixed/1 broke, guided 1/1.

## Status 2026-10-31 12:50 ET
A/B/C done and committed (poster v3). Remaining: user review -> "공개해" -> repo public -> user uploads PDF -> hub done.

## 13:10 ET: added policy local_only (T1 self-signal -> local VLM with checks -> review, no cloud). SROIE 93.4% precision / 19% review / $0; Wild 89.0% / 31.5%. Not yet on the poster (README candidate).

## 13:50 ET: poster v4 (simplified: terms box with oracle/AUC, routing summary table incl. local-only; retry table and Fig C dropped). docs/OVERVIEW.ko.md = Korean narrative + mermaid flow + data-residency checklist.

## 13:40 ET (session cc-3bdbaffc): preview fixes + workflow redesign
Fig A tau=0 label moved off the harness line; companion panel 2 is an HTML ladder (no cut-off; tap a panel title for full screen); workflow_en/kr rebuilt as architecture diagram (local / Gemini / Anthropic boundaries, numbered steps) + compact decision flow + muted details, all numbers read from results JSON. Poster columns 790/790/790. Open question for the user: `cloud_share` in policies/tau_sweep is the share *accepted* at a cloud tier (harness 52%), not the share *sent* (56.3%); poster Fig A x-axis says "sent". Not changed yet.
13:55 ET: resolved. `cloud_share` split into `cloud_sent_share` (image reached a cloud tier) and `cloud_accepted_share` (answer accepted there); Fig A, the poster routing table (now filled from JSON by 10_fill_poster, learned row at the router's cloud share), README and workflow pages use sent. Harness 56% sent / 52% accepted; harness_ladder 19% / 15%. docs/workflow.html removed (superseded by workflow_kr.html).
