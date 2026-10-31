# Routing policies (tau = 0.9; date+total exact match)

| policy | auto-accept | review | T1 | T2 | T3 | T4 | accepted precision (date+total) | leak | USD / 1k | latency med (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| all_local | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 72.7% | 27.3% | 0.0 | 4672 |
| all_qwen | 42.3% | 57.7% | 0.0% | 42.3% | 0.0% | 0.0% | 80.3% | 8.3% | 0.0 | 33322 |
| all_lite | 100.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 97.3% | 2.7% | 0.535 | 1811 |
| all_strong | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 98.0% | 2.0% | 1.423 | 1859 |
| oracle | 100.0% | 0.0% | 72.7% | 0.0% | 27.3% | 0.0% | 98.7% | 1.3% | 0.146 | 5007 |
| router | 100.0% | 0.0% | 43.7% | 0.0% | 56.3% | 0.0% | 95.7% | 4.3% | 0.301 | 5914 |
| harness | 95.7% | 4.3% | 43.7% | 0.0% | 51.7% | 0.3% | 96.9% | 3.0% | 0.369 | 6040 |
| harness_ladder | 96.3% | 3.7% | 43.7% | 16.0% | 36.3% | 0.3% | 95.5% | 4.3% | 0.274 | 6058 |
| router_solo | 100.0% | 0.0% | 72.0% | 0.0% | 28.0% | 0.0% | 91.0% | 9.0% | 0.15 | 5007 |
| harness_solo | 96.3% | 3.7% | 72.0% | 0.0% | 24.3% | 0.0% | 91.7% | 8.0% | 0.203 | 5041 |
| harness_ladder_solo | 97.0% | 3.0% | 72.0% | 8.0% | 17.0% | 0.0% | 90.4% | 9.3% | 0.151 | 5041 |

# Verification waterfall (per VLM tier)

| tier | n | model errors | flagged | caught | leaked | false flags | recall | precision | top flags |
|---|---|---|---|---|---|---|---|---|---|
| t2 | 127 | 25 | 37 | 18 | 7 | 19 | 72.0% | 48.6% | G_ARITH:24, G_AGREE_TOTAL:11, G_AGREE_DATE:5, G_RANGE:1, G_MISSING:1 |
| t3 | 300 | 8 | 20 | 5 | 3 | 15 | 62.5% | 25.0% | G_ARITH:9, G_AGREE_DATE:6, G_AGREE_TOTAL:3, G_DATE:1, G_RANGE:1 |
| t4 | 300 | 6 | 22 | 4 | 2 | 18 | 66.7% | 18.2% | G_ARITH:12, G_AGREE_DATE:7, G_AGREE_TOTAL:3, G_RANGE:2 |
