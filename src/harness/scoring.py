"""scoring.py - Map any engine record onto the three scored fields and compare
with ground truth. Deterministic; shared by 03_score and 04_harness."""

from __future__ import annotations

from . import rules
from .normalize import company_key, norm_company, norm_date, norm_total

FIELDS = ("company", "date", "total")


def predicted_fields(rec: dict | None) -> dict:
    if not rec:
        return {"company": None, "date": None, "total": None}
    if "lines" in rec:                         # tier 1: re-run the CURRENT rules on the stored OCR text
        rr = rules.extract(rec["lines"] or [])
        return {"company": norm_company(rr.company),
                "date": norm_date(rr.date, day_first=True),
                "total": norm_total(rr.total)}
    if "fields" in rec:
        f = rec["fields"] or {}
        return {"company": norm_company(f.get("company")),
                "date": norm_date(f.get("date"), day_first=True),
                "total": norm_total(f.get("total"))}
    data = rec.get("data") or {}              # VLM tiers
    return {"company": norm_company(data.get("vendor")),
            "date": norm_date(data.get("date"), day_first=True),
            "total": norm_total(data.get("total"))}


def _eq(fld: str, a, b) -> bool:
    if fld == "company":
        return company_key(a) == company_key(b)
    return a == b


def correct_fields(pred: dict, gt: dict) -> dict:
    """True/False per field; None when ground truth is missing for that field.
    Company is compared space-insensitively (see normalize.company_key)."""
    return {fld: (None if gt.get(fld) is None else _eq(fld, pred.get(fld), gt[fld])) for fld in FIELDS}


def money_fields_ok(correct: dict) -> bool | None:
    """date and total both right (the fields finance reconciles on)."""
    vals = [correct.get("date"), correct.get("total")]
    if any(v is None for v in vals):
        vals = [v for v in vals if v is not None]
        if not vals:
            return None
    return all(vals)


def all_fields_ok(correct: dict) -> bool | None:
    vals = [v for v in correct.values() if v is not None]
    return all(vals) if vals else None
