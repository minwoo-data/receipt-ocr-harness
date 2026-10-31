# Routing policies (tau = 0.9; date+total exact match)

Tier columns = where the receipt was accepted. Sent to cloud = the image reached a cloud tier (accepted there or not).

| policy | auto-accept | review | sent to cloud | T1 | T2 | T3 | T4 | accepted precision (date+total) | leak | USD / 1k | latency med (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all_local | 100.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 77.3% | 22.7% | 0.0 | 4672 |
| all_qwen | 100.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 83.0% | 17.0% | 0.0 | 28293 |
| all_lite | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% | 100.0% | 0.0% | 97.3% | 2.7% | 0.535 | 1811 |
| all_strong | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 100.0% | 98.0% | 2.0% | 1.423 | 1859 |
| oracle | 100.0% | 0.0% | 22.7% | 77.3% | 0.0% | 22.7% | 0.0% | 98.7% | 1.3% | 0.121 | 4928 |
| router | 100.0% | 0.0% | 55.0% | 45.0% | 0.0% | 55.0% | 0.0% | 95.7% | 4.3% | 0.294 | 5883 |
| harness | 95.7% | 4.3% | 55.0% | 45.0% | 0.0% | 50.3% | 0.3% | 96.9% | 3.0% | 0.362 | 5947 |
| harness_ladder | 96.3% | 3.7% | 18.3% | 45.0% | 36.7% | 14.7% | 0.0% | 94.5% | 5.3% | 0.151 | 26586 |
| router_solo | 100.0% | 0.0% | 24.3% | 75.7% | 0.0% | 24.3% | 0.0% | 91.3% | 8.7% | 0.13 | 4942 |
| harness_solo | 96.0% | 4.0% | 25.7% | 74.3% | 0.0% | 21.3% | 0.3% | 93.4% | 6.3% | 0.2 | 5029 |
| harness_ladder_solo | 96.7% | 3.3% | 8.0% | 74.3% | 17.7% | 4.7% | 0.0% | 91.4% | 8.3% | 0.091 | 5064 |
| local_only | 81.7% | 18.3% | 0.0% | 45.0% | 36.7% | 0.0% | 0.0% | 93.5% | 5.3% | 0.0 | 25298 |
| local_only_solo | 92.0% | 8.0% | 0.0% | 74.3% | 17.7% | 0.0% | 0.0% | 90.9% | 8.3% | 0.0 | 5064 |

# Verification waterfall (per VLM tier)

| tier | n | model errors | flagged | caught | leaked | false flags | recall | precision | top flags |
|---|---|---|---|---|---|---|---|---|---|
| t2 | 300 | 51 | 87 | 38 | 13 | 49 | 74.5% | 43.7% | G_ARITH:57, G_AGREE_TOTAL:24, G_AGREE_DATE:12, G_DATE:4, G_RANGE:1 |
| t3 | 300 | 8 | 20 | 5 | 3 | 15 | 62.5% | 25.0% | G_ARITH:9, G_AGREE_DATE:6, G_AGREE_TOTAL:3, G_DATE:1, G_RANGE:1 |
| t4 | 300 | 6 | 22 | 4 | 2 | 18 | 66.7% | 18.2% | G_ARITH:12, G_AGREE_DATE:7, G_AGREE_TOTAL:3, G_RANGE:2 |
