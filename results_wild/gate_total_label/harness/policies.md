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
| harness | 77.5% | 22.5% | 84.0% | 16.0% | 0.0% | 58.0% | 3.5% | 95.5% | 3.5% | 0.816 | 5207 |
| harness_ladder | 80.5% | 19.5% | 33.0% | 16.0% | 51.0% | 12.5% | 1.0% | 94.4% | 4.5% | 0.47 | 30000 |
| router_solo | 100.0% | 0.0% | 43.0% | 57.0% | 0.0% | 43.0% | 0.0% | 90.0% | 10.0% | 0.227 | 4066 |
| harness_solo | 88.5% | 11.5% | 43.0% | 57.0% | 0.0% | 29.0% | 2.5% | 89.3% | 9.5% | 0.427 | 4150 |
| harness_ladder_solo | 90.0% | 10.0% | 16.5% | 57.0% | 26.5% | 5.5% | 1.0% | 88.3% | 10.5% | 0.246 | 4460 |
| local_only | 67.0% | 33.0% | 0.0% | 16.0% | 51.0% | 0.0% | 0.0% | 94.0% | 4.0% | 0.0 | 28437 |
| local_only_solo | 83.5% | 16.5% | 0.0% | 57.0% | 26.5% | 0.0% | 0.0% | 87.4% | 10.5% | 0.0 | 4460 |

# Verification waterfall (per VLM tier)

| tier | n | model errors | flagged | caught | leaked | false flags | recall | precision | top flags |
|---|---|---|---|---|---|---|---|---|---|
| t2 | 200 | 27 | 73 | 21 | 6 | 52 | 77.8% | 28.8% | G_ARITH:37, G_AGREE_DATE:28, G_AGREE_TOTAL:13, G_RANGE:3, G_TOTAL_ROUNDED:2 |
| t3 | 200 | 13 | 59 | 7 | 6 | 52 | 53.8% | 11.9% | G_ARITH:24, G_AGREE_DATE:21, G_AGREE_TOTAL:12, G_RANGE:6, G_MISSING:3 |
| t4 | 200 | 13 | 55 | 7 | 6 | 48 | 53.8% | 12.7% | G_AGREE_DATE:21, G_ARITH:18, G_AGREE_TOTAL:13, G_RANGE:6, G_MISSING:3 |
