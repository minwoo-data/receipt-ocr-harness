# Round 1 - plan-abc.md

Verdicts: LLM REVISE / Architect REVISE / EndUser REVISE.

## Synthesis (deduplicated, by priority)

1. **Single input contract** (Architect high). A, B, C each re-derive correctness/flags from different files; the poster numbers come from `results/harness/per_receipt.jsonl`. Drift risk. -> ACCEPT: per_receipt.jsonl is the sole source of correctness, flags, latency, cost for all three; A may add raw tier-1 records for features only.
2. **B is underspecified and duplicates the policy simulator** (LLM high, Architect high). -> ACCEPT: implement `hedge` as a policy branch in 04_harness `decide()` with parameters D and local-latency scale; four explicit arrival rules; cloud share counts fired calls; both arms flagged -> review; T4 never called; sanity checks become tests.
3. **A replay rule and acceptance unspecified** (LLM high, EndUser low). -> ACCEPT: escalated receipts receive T3 recorded correctness accepted blindly (same as `router`/`oracle`); the learned score replaces the whole T1 self-signal; acceptance = two explicit conditions; Wild transfer compared with the Wild `router` baseline.
4. **A feature schema** (LLM med, Architect high). -> ACCEPT: `src/harness/features.py` with `feature_names`, `schema_version`, allowed source keys; reason indicators from the six `rule_reasons` strings in rules.py; aspect ratio and keyword strength DROPPED (not stored in tier-1 records).
5. **C leak definition and provenance** (LLM high, Architect med). -> ACCEPT: leak = waterfall definition (tier answer wrong on date or total AND empty flag list), all six tier-dataset pairs (SROIE t2/t3/t4, Wild t2/t3/t4); classes derived by code from per_receipt + OCR lines (no hand labels), written to `<root>/leaks/leaks.jsonl` and rendered `leaks.md`.
6. **Background, glossary, run commands, poster targets** (EndUser high x2, med; LLM med, low). -> ACCEPT: Background paragraph, glossary of T1-T4 and roots, a Run line per section, poster edit targets named (template + findings.json; html/pdf regenerated).
7. **Numbers typed into prose go stale** (Architect low). -> ACCEPT: prose numbers labelled "run of 2026-10-31"; summaries read policies.json / waterfall.json.
8. Per-dataset output roots (Architect med). -> ACCEPT: `<results_root>/learned_router/`, `<results_root>/hedge/`, `<results_root>/leaks/`.

## Open questions answered by the author
- B starts at T2 (no T1 stage), so it isolates the time-budget question; cloud share counts fired calls.
- A label = T1 wrong on date OR total under the manifest's day_first, read from per_receipt (same axis as the oracle row).
- Re-run order after any 04_harness change: 04 -> 12 (leaks) -> 14 (learned router) -> 06 -> 10 -> 09; written into the plan's table.
- Aspect ratio dropped, so images are not needed to re-run A.
- Wild t2 and t4 leaks are included (63 rows), classification is by code so the cost does not double.

## Applied
No `--apply` flag: triad left the original untouched. The author rewrote `docs/plan-abc.md` (v2) with every ACCEPT above; round 2 reviews v2.
