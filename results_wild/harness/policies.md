# Routing policies (tau = 0.9; date+total exact match)

| policy | auto-accept | review | T1 | T2 | T3 | T4 | accepted precision (date+total) | leak | USD / 1k | latency med (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| all_local | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 55.0% | 45.0% | 0.0 | 3306 |
| all_qwen | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | n/a | 0.0% | None | 0 |
| all_lite | 100.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 86.5% | 13.5% | 0.528 | 1596 |
| all_strong | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 86.5% | 13.5% | 1.406 | 1672 |
| oracle | 100.0% | 0.0% | 55.0% | 0.0% | 45.0% | 0.0% | 90.0% | 10.0% | 0.238 | 4070 |
| router | 100.0% | 0.0% | 16.0% | 0.0% | 84.0% | 0.0% | 87.0% | 13.0% | 0.444 | 4825 |
| harness | 78.5% | 21.5% | 16.0% | 0.0% | 59.0% | 3.5% | 88.5% | 9.0% | 0.801 | 5175 |
| harness_ladder | 78.5% | 21.5% | 16.0% | 0.0% | 59.0% | 3.5% | 88.5% | 9.0% | 0.801 | 5175 |
| router_solo | 100.0% | 0.0% | 54.0% | 0.0% | 46.0% | 0.0% | 83.0% | 17.0% | 0.243 | 4192 |
| harness_solo | 88.5% | 11.5% | 54.0% | 0.0% | 32.0% | 2.5% | 83.6% | 14.5% | 0.443 | 4300 |
| harness_ladder_solo | 88.5% | 11.5% | 54.0% | 0.0% | 32.0% | 2.5% | 83.6% | 14.5% | 0.443 | 4300 |

# Verification waterfall (per VLM tier)

| tier | n | model errors | flagged | caught | leaked | false flags | recall | precision | top flags |
|---|---|---|---|---|---|---|---|---|---|
| t2 | 0 | 0 | 0 | 0 | 0 | 0 | n/a | n/a |  |
| t3 | 200 | 27 | 57 | 10 | 17 | 47 | 37.0% | 17.5% | G_ARITH:24, G_AGREE_DATE:21, G_AGREE_TOTAL:12, G_RANGE:6, G_MISSING:3 |
| t4 | 200 | 27 | 54 | 11 | 16 | 43 | 40.7% | 20.4% | G_AGREE_DATE:21, G_ARITH:18, G_AGREE_TOTAL:13, G_RANGE:6, G_MISSING:3 |
