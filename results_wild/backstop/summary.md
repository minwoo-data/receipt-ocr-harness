# Backstops for leaks (auto-accepted but wrong), results_wild, n = 200, tau = 0.9

## cloud (harness): 157 auto-accepted, 8 leaks {'T1': 4, 'T3': 4}; misstated total 279.97, 1 leaks off by under 0.10

Random audit of auto-accepted receipts (exact expectation, sampling without replacement)

| audit | receipts audited | per 1k | expected leaks caught | share of leaks | P(find >= 1 leak) |
|---|---|---|---|---|---|
| 2% | 3 | 15.0 | 0.15 | 2% | 15% |
| 5% | 8 | 40.0 | 0.41 | 5% | 35% |
| 10% | 16 | 80.0 | 0.82 | 10% | 59% |

Top X% of auto-accepted receipts by accepted total, re-read by T4; disagreement goes to review

| top X% | re-read | leaks caught | correct sent to review | extra review per 1k | extra USD per 1k | extra images to cloud | misstated amount covered |
|---|---|---|---|---|---|---|---|
| 5% | 8 | 0 of 8 | 0 | 0.0 | 0.058 | 0% | 0% of 279.97 |
| 10% | 15 | 0 of 8 | 0 | 0.0 | 0.107 | 0% | 0% of 279.97 |
| 20% | 28 | 1 of 8 | 0 | 5.0 | 0.199 | 0% | 0% of 279.97 |
| 30% | 43 | 1 of 8 | 1 | 10.0 | 0.304 | 2% | 0% of 279.97 |
| 100% | 150 | 5 of 8 | 3 | 40.0 | 1.049 | 16% | 100% of 279.97 |

## local_only (local_only): 136 auto-accepted, 9 leaks {'T1': 4, 'T2': 5}; misstated total 280.11, 1 leaks off by under 0.10

Random audit of auto-accepted receipts (exact expectation, sampling without replacement)

| audit | receipts audited | per 1k | expected leaks caught | share of leaks | P(find >= 1 leak) |
|---|---|---|---|---|---|
| 2% | 3 | 15.0 | 0.2 | 2% | 19% |
| 5% | 7 | 35.0 | 0.46 | 5% | 39% |
| 10% | 14 | 70.0 | 0.93 | 10% | 64% |
