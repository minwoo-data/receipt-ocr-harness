# Gate experiment: total_label on results_wild (held-out (gate frozen at 07a5a7a))

verify.py sha256 `7b929ffe2419740b…`; n = 200. Verdicts changed from pass to flagged: 5 (2 were wrong answers that had leaked, 3 were right answers now flagged).

| reader alone | model errors | caught before | caught after | leaked after | false flags before | after |
|---|---|---|---|---|---|---|
| t2 | 38 | 26 | 27 | 11 | 44 | 45 |
| t3 | 27 | 10 | 11 | 16 | 47 | 48 |
| t4 | 27 | 11 | 11 | 16 | 43 | 44 |

| policy | accepted correct | review | sent to cloud | USD / 1k | leak |
|---|---|---|---|---|---|
| harness | 88.5% → 89.0% | 21.5% → 22.5% | 84.0% → 84.0% | 0.801 → 0.816 | 9.0% → 8.5% |
| local_only | 89.0% → 89.6% | 31.5% → 32.5% | 0.0% → 0.0% | 0.0 → 0.0 | 7.5% → 7.0% |
| harness_ladder | 88.3% → 88.8% | 18.5% → 19.5% | 31.5% → 32.5% | 0.448 → 0.468 | 9.5% → 9.0% |

| key | tier | new flag | answer was |
|---|---|---|---|
| W0145_62afa3fa08bb | t2 | G_TOTAL_TENDER | wrong (leak caught) |
| W0145_62afa3fa08bb | t3 | G_TOTAL_TENDER | wrong (leak caught) |
| W0170_e5114eee5454 | t2 | G_TOTAL_ROUNDED | right (false flag) |
| W0170_e5114eee5454 | t3 | G_TOTAL_ROUNDED | right (false flag) |
| W0170_e5114eee5454 | t4 | G_TOTAL_ROUNDED | right (false flag) |
