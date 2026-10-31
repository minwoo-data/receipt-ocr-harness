# Learned escalation signal (results_wild; fit on results, scored on results_wild; n=200)

- AUC (tier-1 wrong vs right): 0.818
- rule router: cloud share 84.0%, precision 94.0%
- learned, precision at the router's cloud share: 93.5%
- learned, cloud share needed for the router's precision: 75.5%
- oracle: cloud share 37.0%, precision 96.5%
- verdict: PARTIAL

| coefficient | feature |
|---|---|
| +1.26 | reason_date_not_found |
| +0.83 | total_abs_diff_capped |
| +0.60 | rapid_bottom_money_tokens |
| -0.55 | rapid_mean_conf |
| -0.49 | signal_complete |
| +0.49 | reason_total_no_keyword_fallback_max |
| +0.42 | reason_total_multiple_keyword_amounts |
| +0.41 | tess_mean_conf |
| +0.25 | reason_total_not_found |
| -0.14 | rapid_line_count |
| +0.11 | reason_total_multiple_strong_amounts |
| -0.10 | signal_agree |
| +0.07 | reason_company_not_found |
| +0.00 | rapid_low_conf_share |
