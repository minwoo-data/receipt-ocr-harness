# Gate experiment: total_label on results_wild (held-out (gate frozen at 07a5a7a))

verify.py sha256 `7b929ffe2419740b…`; n = 200. Verdicts changed from pass to flagged: 5 (2 were wrong answers that had leaked, 3 were right answers now flagged).

| reader alone | model errors | caught before | caught after | leaked after | false flags before | after |
|---|---|---|---|---|---|---|
| t2 | 27 | 20 | 21 | 6 | 51 | 52 |
| t3 | 13 | 6 | 7 | 6 | 51 | 52 |
| t4 | 13 | 7 | 7 | 6 | 47 | 48 |

| policy | accepted correct | review | sent to cloud | USD / 1k | leak |
|---|---|---|---|---|---|
| harness | 94.9% → 95.5% | 21.5% → 22.5% | 84.0% → 84.0% | 0.801 → 0.816 | 4.0% → 3.5% |
| local_only | 93.4% → 94.0% | 32.0% → 33.0% | 0.0% → 0.0% | 0.0 → 0.0 | 4.5% → 4.0% |
| harness_ladder | 93.9% → 94.4% | 18.5% → 19.5% | 32.0% → 33.0% | 0.45 → 0.47 | 5.0% → 4.5% |

| key | tier | new flag | answer was |
|---|---|---|---|
| W0145_62afa3fa08bb | t2 | G_TOTAL_TENDER | wrong (leak caught) |
| W0145_62afa3fa08bb | t3 | G_TOTAL_TENDER | wrong (leak caught) |
| W0170_e5114eee5454 | t2 | G_TOTAL_ROUNDED | right (false flag) |
| W0170_e5114eee5454 | t3 | G_TOTAL_ROUNDED | right (false flag) |
| W0170_e5114eee5454 | t4 | G_TOTAL_ROUNDED | right (false flag) |
