# Round 2 - plan-abc.md v2

Verdicts: Architect PASS / EndUser PASS / LLM REVISE.

## Issues and decisions
- Architect (med): decide(row, policy, params) with a params dict; hedge rows carry latency_kind=wall -> ACCEPT. per_receipt.schema.json written by 04 and asserted by 12/14 -> ACCEPT. run_all.py -> ACCEPT. Hedge rows live in <root>/hedge/, not in policies.md -> decided.
- EndUser (med): table order B -> C -> A -> ACCEPT. (low) Wild baselines in Why, dataset intro, unit -> ACCEPT.
- LLM (high): both_wrong checked first -> ACCEPT. Threshold grid, baseline source, no-interpolation rules, not-reached handling -> ACCEPT. (med) feature edge cases -> ACCEPT. Open questions: null money_ok rows excluded; per-root figure files; explicit --results flags -> all written into v2.1.

## Applied
Author applied every item to docs/plan-abc.md (v2.1). No `--apply` flag was given, so triad itself wrote nothing to the source.
