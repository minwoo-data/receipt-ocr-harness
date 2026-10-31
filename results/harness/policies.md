# Routing policies (tau = 0.9; date+total exact match)

Tier columns = where the receipt was accepted. Sent to cloud = the image reached a cloud tier (accepted there or not).

| policy | auto-accept | review | sent to cloud | T1 | T2 | T3 | T4 | accepted precision (date+total) | leak | USD / 1k | latency med (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all_local | 100.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 72.7% | 27.3% | 0.0 | 4672 |
| all_qwen | 100.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 83.0% | 17.0% | 0.0 | 28293 |
| all_lite | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% | 100.0% | 0.0% | 97.3% | 2.7% | 0.535 | 1811 |
| all_strong | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 100.0% | 98.0% | 2.0% | 1.423 | 1859 |
| oracle | 100.0% | 0.0% | 27.3% | 72.7% | 0.0% | 27.3% | 0.0% | 98.7% | 1.3% | 0.146 | 5007 |
| router | 100.0% | 0.0% | 56.3% | 43.7% | 0.0% | 56.3% | 0.0% | 95.7% | 4.3% | 0.301 | 5914 |
| harness | 95.7% | 4.3% | 56.3% | 43.7% | 0.0% | 51.7% | 0.3% | 96.9% | 3.0% | 0.369 | 6040 |
| harness_ladder | 96.3% | 3.7% | 19.0% | 43.7% | 37.3% | 15.3% | 0.0% | 94.5% | 5.3% | 0.155 | 27114 |
| router_solo | 100.0% | 0.0% | 28.0% | 72.0% | 0.0% | 28.0% | 0.0% | 91.0% | 9.0% | 0.15 | 5007 |
| harness_solo | 96.3% | 3.7% | 28.0% | 72.0% | 0.0% | 24.3% | 0.0% | 91.7% | 8.0% | 0.203 | 5041 |
| harness_ladder_solo | 97.0% | 3.0% | 9.7% | 72.0% | 18.3% | 6.7% | 0.0% | 89.7% | 10.0% | 0.095 | 5081 |
| local_only | 81.0% | 19.0% | 0.0% | 43.7% | 37.3% | 0.0% | 0.0% | 93.4% | 5.3% | 0.0 | 26712 |
| local_only_solo | 90.3% | 9.7% | 0.0% | 72.0% | 18.3% | 0.0% | 0.0% | 88.9% | 10.0% | 0.0 | 5081 |

# Verification waterfall (per VLM tier)

| tier | n | model errors | flagged | caught | leaked | false flags | recall | precision | top flags |
|---|---|---|---|---|---|---|---|---|---|
| t2 | 300 | 51 | 87 | 38 | 13 | 49 | 74.5% | 43.7% | G_ARITH:57, G_AGREE_TOTAL:24, G_AGREE_DATE:12, G_DATE:4, G_RANGE:1 |
| t3 | 300 | 8 | 20 | 5 | 3 | 15 | 62.5% | 25.0% | G_ARITH:9, G_AGREE_DATE:6, G_AGREE_TOTAL:3, G_DATE:1, G_RANGE:1 |
| t4 | 300 | 6 | 22 | 4 | 2 | 18 | 66.7% | 18.2% | G_ARITH:12, G_AGREE_DATE:7, G_AGREE_TOTAL:3, G_RANGE:2 |
