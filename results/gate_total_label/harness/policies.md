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
| harness | 95.3% | 4.7% | 55.0% | 45.0% | 0.0% | 50.0% | 0.3% | 97.2% | 2.7% | 0.366 | 5947 |
| harness_ladder | 96.0% | 4.0% | 20.0% | 45.0% | 35.0% | 16.0% | 0.0% | 96.2% | 3.7% | 0.165 | 26818 |
| router_solo | 100.0% | 0.0% | 24.3% | 75.7% | 0.0% | 24.3% | 0.0% | 91.3% | 8.7% | 0.13 | 4942 |
| harness_solo | 96.0% | 4.0% | 25.7% | 74.3% | 0.0% | 21.3% | 0.3% | 93.4% | 6.3% | 0.2 | 5029 |
| harness_ladder_solo | 96.3% | 3.7% | 9.3% | 74.3% | 16.3% | 5.7% | 0.0% | 92.7% | 7.0% | 0.103 | 5064 |
| local_only | 80.0% | 20.0% | 0.0% | 45.0% | 35.0% | 0.0% | 0.0% | 95.4% | 3.7% | 0.0 | 25298 |
| local_only_solo | 90.7% | 9.3% | 0.0% | 74.3% | 16.3% | 0.0% | 0.0% | 92.3% | 7.0% | 0.0 | 5064 |

# Verification waterfall (per VLM tier)

| tier | n | model errors | flagged | caught | leaked | false flags | recall | precision | top flags |
|---|---|---|---|---|---|---|---|---|---|
| t2 | 300 | 51 | 95 | 46 | 5 | 49 | 90.2% | 48.4% | G_ARITH:57, G_AGREE_TOTAL:24, G_AGREE_DATE:12, G_TOTAL_ROUNDED:7, G_DATE:4 |
| t3 | 300 | 8 | 21 | 6 | 2 | 15 | 75.0% | 28.6% | G_ARITH:9, G_AGREE_DATE:6, G_AGREE_TOTAL:3, G_TOTAL_TENDER:1, G_DATE:1 |
| t4 | 300 | 6 | 23 | 5 | 1 | 18 | 83.3% | 21.7% | G_ARITH:12, G_AGREE_DATE:7, G_AGREE_TOTAL:3, G_RANGE:2, G_TOTAL_TENDER:1 |
