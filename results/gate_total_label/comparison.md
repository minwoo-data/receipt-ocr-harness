# Gate experiment: total_label on results (dev (gate designed here))

verify.py sha256 `7b929ffe2419740b…`; n = 300. Verdicts changed from pass to flagged: 10 (10 were wrong answers that had leaked, 0 were right answers now flagged).

| reader alone | model errors | caught before | caught after | leaked after | false flags before | after |
|---|---|---|---|---|---|---|
| t2 | 51 | 38 | 46 | 5 | 49 | 49 |
| t3 | 8 | 5 | 6 | 2 | 15 | 15 |
| t4 | 6 | 4 | 5 | 1 | 18 | 18 |

| policy | accepted correct | review | sent to cloud | USD / 1k | leak |
|---|---|---|---|---|---|
| harness | 96.9% → 97.2% | 4.3% → 4.7% | 56.3% → 56.3% | 0.369 → 0.374 | 3.0% → 2.7% |
| local_only | 93.4% → 95.4% | 19.0% → 20.7% | 0.0% → 0.0% | 0.0 → 0.0 | 5.3% → 3.7% |
| harness_ladder | 94.5% → 96.2% | 3.7% → 4.0% | 19.0% → 20.7% | 0.155 → 0.169 | 5.3% → 3.7% |

| key | tier | new flag | answer was |
|---|---|---|---|
| X51005675914 | t2 | G_TOTAL_ROUNDED | wrong (leak caught) |
| X51006401845 | t2 | G_TOTAL_TENDER | wrong (leak caught) |
| X51005684949 | t3 | G_TOTAL_TENDER | wrong (leak caught) |
| X51005684949 | t4 | G_TOTAL_TENDER | wrong (leak caught) |
| X51007846355 | t2 | G_TOTAL_ROUNDED | wrong (leak caught) |
| X51005230648 | t2 | G_TOTAL_ROUNDED | wrong (leak caught) |
| X51008142005 | t2 | G_TOTAL_ROUNDED | wrong (leak caught) |
| X51005442344 | t2 | G_TOTAL_ROUNDED | wrong (leak caught) |
| X51008142032 | t2 | G_TOTAL_ROUNDED | wrong (leak caught) |
| X51008142031 | t2 | G_TOTAL_ROUNDED | wrong (leak caught) |
