# Backstops for leaks (auto-accepted but wrong), results, n = 300, tau = 0.9

## cloud (harness): 287 auto-accepted, 9 leaks {'T1': 7, 'T3': 2}; misstated total 6.47, 7 leaks off by under 0.10

Random audit of auto-accepted receipts (exact expectation, sampling without replacement)

| audit | receipts audited | per 1k | expected leaks caught | share of leaks | P(find >= 1 leak) |
|---|---|---|---|---|---|
| 2% | 6 | 20.0 | 0.19 | 2% | 18% |
| 5% | 14 | 46.7 | 0.44 | 5% | 37% |
| 10% | 29 | 96.7 | 0.91 | 10% | 62% |

Top X% of auto-accepted receipts by accepted total, re-read by T4; disagreement goes to review

| top X% | re-read | leaks caught | correct sent to review | extra review per 1k | extra USD per 1k | extra images to cloud | misstated amount covered |
|---|---|---|---|---|---|---|---|
| 5% | 14 | 0 of 9 | 0 | 0.0 | 0.067 | 2% | 0% of 6.47 |
| 10% | 29 | 0 of 9 | 0 | 0.0 | 0.138 | 4% | 0% of 6.47 |
| 20% | 57 | 0 of 9 | 0 | 0.0 | 0.272 | 8% | 0% of 6.47 |
| 30% | 86 | 3 of 9 | 0 | 10.0 | 0.409 | 13% | 1% of 6.47 |
| 100% | 286 | 7 of 9 | 1 | 26.7 | 1.355 | 45% | 79% of 6.47 |

## local_only (local_only): 245 auto-accepted, 16 leaks {'T1': 7, 'T2': 9}; misstated total 12.78, 11 leaks off by under 0.10

Random audit of auto-accepted receipts (exact expectation, sampling without replacement)

| audit | receipts audited | per 1k | expected leaks caught | share of leaks | P(find >= 1 leak) |
|---|---|---|---|---|---|
| 2% | 5 | 16.7 | 0.33 | 2% | 29% |
| 5% | 12 | 40.0 | 0.78 | 5% | 56% |
| 10% | 24 | 80.0 | 1.57 | 10% | 82% |
