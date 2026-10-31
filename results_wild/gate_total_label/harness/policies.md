# Routing policies (tau = 0.9; date+total exact match)

Tier columns = where the receipt was accepted. Sent to cloud = the image reached a cloud tier (accepted there or not).

| policy | auto-accept | review | sent to cloud | T1 | T2 | T3 | T4 | accepted precision (date+total) | leak | USD / 1k | latency med (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all_local | 100.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 55.0% | 45.0% | 0.0 | 3306 |
| all_qwen | 100.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 81.0% | 19.0% | 0.0 | 26197 |
| all_lite | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% | 100.0% | 0.0% | 86.5% | 13.5% | 0.528 | 1596 |
| all_strong | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 100.0% | 86.5% | 13.5% | 1.406 | 1672 |
| oracle | 100.0% | 0.0% | 45.0% | 55.0% | 0.0% | 45.0% | 0.0% | 90.0% | 10.0% | 0.238 | 4070 |
| router | 100.0% | 0.0% | 84.0% | 16.0% | 0.0% | 84.0% | 0.0% | 87.0% | 13.0% | 0.444 | 4825 |
| harness | 77.5% | 22.5% | 84.0% | 16.0% | 0.0% | 58.0% | 3.5% | 89.0% | 8.5% | 0.816 | 5207 |
| harness_ladder | 80.5% | 19.5% | 32.5% | 16.0% | 51.5% | 12.0% | 1.0% | 88.8% | 9.0% | 0.468 | 30000 |
| router_solo | 100.0% | 0.0% | 46.0% | 54.0% | 0.0% | 46.0% | 0.0% | 83.0% | 17.0% | 0.243 | 4192 |
| harness_solo | 88.0% | 12.0% | 46.0% | 54.0% | 0.0% | 31.5% | 2.5% | 83.5% | 14.5% | 0.45 | 4300 |
| harness_ladder_solo | 89.5% | 10.5% | 16.5% | 54.0% | 29.5% | 5.0% | 1.0% | 83.2% | 15.0% | 0.253 | 5070 |
| local_only | 67.5% | 32.5% | 0.0% | 16.0% | 51.5% | 0.0% | 0.0% | 89.6% | 7.0% | 0.0 | 28437 |
| local_only_solo | 83.5% | 16.5% | 0.0% | 54.0% | 29.5% | 0.0% | 0.0% | 83.2% | 14.0% | 0.0 | 5070 |

# Verification waterfall (per VLM tier)

| tier | n | model errors | flagged | caught | leaked | false flags | recall | precision | top flags |
|---|---|---|---|---|---|---|---|---|---|
| t2 | 200 | 38 | 72 | 27 | 11 | 45 | 71.0% | 37.5% | G_ARITH:37, G_AGREE_DATE:28, G_AGREE_TOTAL:13, G_RANGE:3, G_TOTAL_ROUNDED:2 |
| t3 | 200 | 27 | 59 | 11 | 16 | 48 | 40.7% | 18.6% | G_ARITH:24, G_AGREE_DATE:21, G_AGREE_TOTAL:12, G_RANGE:6, G_MISSING:3 |
| t4 | 200 | 27 | 55 | 11 | 16 | 44 | 40.7% | 20.0% | G_AGREE_DATE:21, G_ARITH:18, G_AGREE_TOTAL:13, G_RANGE:6, G_MISSING:3 |
