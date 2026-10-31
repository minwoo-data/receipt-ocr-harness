# Routing policies (tau = 0.9; date+total exact match)

Tier columns = where the receipt was accepted. Sent to cloud = the image reached a cloud tier (accepted there or not).

| policy | auto-accept | review | sent to cloud | T1 | T2 | T3 | T4 | accepted precision (date+total) | leak | USD / 1k | latency med (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all_local | 100.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 63.0% | 37.0% | 0.0 | 3306 |
| all_qwen | 100.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 86.5% | 13.5% | 0.0 | 26197 |
| all_lite | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% | 100.0% | 0.0% | 93.5% | 6.5% | 0.528 | 1596 |
| all_strong | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 100.0% | 93.5% | 6.5% | 1.406 | 1672 |
| oracle | 100.0% | 0.0% | 37.0% | 63.0% | 0.0% | 37.0% | 0.0% | 96.5% | 3.5% | 0.195 | 4006 |
| router | 100.0% | 0.0% | 84.0% | 16.0% | 0.0% | 84.0% | 0.0% | 94.0% | 6.0% | 0.444 | 4825 |
| harness | 78.5% | 21.5% | 84.0% | 16.0% | 0.0% | 59.0% | 3.5% | 94.9% | 4.0% | 0.801 | 5175 |
| harness_ladder | 81.5% | 18.5% | 32.0% | 16.0% | 52.0% | 12.5% | 1.0% | 93.9% | 5.0% | 0.45 | 29910 |
| router_solo | 100.0% | 0.0% | 43.0% | 57.0% | 0.0% | 43.0% | 0.0% | 90.0% | 10.0% | 0.227 | 4066 |
| harness_solo | 89.0% | 11.0% | 43.0% | 57.0% | 0.0% | 29.5% | 2.5% | 89.3% | 9.5% | 0.42 | 4150 |
| harness_ladder_solo | 90.5% | 9.5% | 16.0% | 57.0% | 27.0% | 5.5% | 1.0% | 88.4% | 10.5% | 0.236 | 4460 |
| local_only | 68.0% | 32.0% | 0.0% | 16.0% | 52.0% | 0.0% | 0.0% | 93.4% | 4.5% | 0.0 | 28437 |
| local_only_solo | 84.0% | 16.0% | 0.0% | 57.0% | 27.0% | 0.0% | 0.0% | 87.5% | 10.5% | 0.0 | 4460 |

# Verification waterfall (per VLM tier)

| tier | n | model errors | flagged | caught | leaked | false flags | recall | precision | top flags |
|---|---|---|---|---|---|---|---|---|---|
| t2 | 200 | 27 | 71 | 20 | 7 | 51 | 74.1% | 28.2% | G_ARITH:37, G_AGREE_DATE:28, G_AGREE_TOTAL:13, G_RANGE:3, G_DATE:2 |
| t3 | 200 | 13 | 57 | 6 | 7 | 51 | 46.2% | 10.5% | G_ARITH:24, G_AGREE_DATE:21, G_AGREE_TOTAL:12, G_RANGE:6, G_MISSING:3 |
| t4 | 200 | 13 | 54 | 7 | 6 | 47 | 53.8% | 13.0% | G_AGREE_DATE:21, G_ARITH:18, G_AGREE_TOTAL:13, G_RANGE:6, G_MISSING:3 |
