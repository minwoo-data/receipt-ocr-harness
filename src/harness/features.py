"""features.py - Tier-1 inference-time features for the learned escalation
signal (plan §A). Only tier-1 records and the harness `signal` field are read;
no ground truth, no cloud output. ALLOWED_SOURCE_KEYS is what a leakage test
asserts against.
"""

from __future__ import annotations

import re

SCHEMA_VERSION = 1
RULE_REASONS = ("total_not_found", "total_multiple_strong_amounts", "total_multiple_keyword_amounts",
                "total_no_keyword_fallback_max", "date_not_found", "company_not_found")
ALLOWED_SOURCE_KEYS = {"rapid": {"mean_conf", "low_conf_share", "lines", "rule_reasons", "fields", "total_candidates"},
                       "tess": {"mean_conf", "fields"},
                       "signal": {"agree", "complete", "conf"}}
_MONEY = re.compile(r"\d+\.\d{2}")

FEATURE_NAMES = ["rapid_mean_conf", "rapid_low_conf_share", "rapid_line_count", "rapid_bottom_money_tokens",
                 "tess_mean_conf", *[f"reason_{r}" for r in RULE_REASONS], "signal_agree", "signal_complete",
                 "total_abs_diff_capped"]


def features(rapid: dict | None, tess: dict | None, signal: dict) -> dict:
    rapid = rapid or {}
    tess = tess or {}
    lines = rapid.get("lines") or []
    bottom = lines[len(lines) // 2:]
    reasons = set(rapid.get("rule_reasons") or [])
    rt = (rapid.get("fields") or {}).get("total")
    tt = (tess.get("fields") or {}).get("total")
    diff = 100.0 if rt is None or tt is None else min(100.0, abs(float(rt) - float(tt)))
    f = {
        "rapid_mean_conf": float(rapid.get("mean_conf") or 0.0),
        "rapid_low_conf_share": float(rapid.get("low_conf_share") if rapid.get("low_conf_share") is not None else 1.0),
        "rapid_line_count": float(len(lines)),
        "rapid_bottom_money_tokens": float(sum(len(_MONEY.findall(l)) for l in bottom)),
        "tess_mean_conf": float(tess.get("mean_conf") or 0.0),
        **{f"reason_{r}": float(r in reasons) for r in RULE_REASONS},
        "signal_agree": float(bool(signal.get("agree"))),
        "signal_complete": float(bool(signal.get("complete"))),
        "total_abs_diff_capped": diff,
    }
    return {k: f[k] for k in FEATURE_NAMES}
