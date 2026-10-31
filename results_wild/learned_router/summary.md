# Learned escalation signal (results_wild; fit on results, scored on results_wild; n=200)

- AUC (tier-1 wrong vs right): 0.866
- rule router: cloud share 84.0%, precision 87.0%
- learned, precision at the router's cloud share: 87.5%
- learned, cloud share needed for the router's precision: 80.0%
- oracle: cloud share 45.0%, precision 90.0%
- verdict: WIN

| coefficient | feature |
|---|---|
| +1.43 | reason_date_not_found |
| -0.93 | signal_complete |
| +0.83 | total_abs_diff_capped |
| +0.64 | rapid_bottom_money_tokens |
| -0.54 | rapid_mean_conf |
| +0.45 | tess_mean_conf |
| +0.25 | reason_total_no_keyword_fallback_max |
| -0.21 | signal_agree |
| +0.20 | reason_total_not_found |
| -0.17 | rapid_line_count |
| -0.16 | reason_company_not_found |
| +0.14 | reason_total_multiple_keyword_amounts |
| -0.03 | reason_total_multiple_strong_amounts |
| +0.00 | rapid_low_conf_share |
