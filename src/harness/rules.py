"""rules.py - Deterministic field extraction from plain OCR text (tier 1).

Input: a list of text lines (top to bottom) as produced by a traditional OCR
engine. Output: company / date / total candidates plus the reasons the rules
could not decide. This is intentionally simple and transparent: the point of
the experiment is to measure how far cheap rules get and when to escalate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .normalize import norm_company, norm_date, norm_total

_TOTAL_KEYS = re.compile(
    r"\b(grand\s*total|total\s*amount|total\s*due|amount\s*due|net\s*total|"
    r"total\s*payable|total\s*sales|rounded\s*total|total|jumlah|amount)\b",
    re.IGNORECASE,
)
_TOTAL_EXCLUDE = re.compile(
    r"\b(sub\s*-?\s*total|subtotal|total\s*(qty|quantity|items?|savings?|discount)|"
    r"gst|tax|vat|change|cash|tendered|rounding|before)\b",
    re.IGNORECASE,
)
_MONEY = re.compile(r"(?<![\d.])-?\d{1,3}(?:,\d{3})*\.\d{2}(?![\d])|(?<![\d.])-?\d+\.\d{2}(?![\d])")
_DATE_HINT = re.compile(
    r"\d{1,4}\s*[/\-.]\s*\d{1,2}\s*[/\-.]\s*\d{1,4}|\d{1,2}\s*[-/ ]?\s*[A-Za-z]{3,9}\s*[-/ ]?\s*\d{2,4}",
)
_COMPANY_SKIP = re.compile(
    r"^(tax\s*invoice|invoice|receipt|cash\s*bill|bill|welcome|thank|tel|fax|gst|"
    r"no\.?|www\.|http|\d+$)",
    re.IGNORECASE,
)
_COMPANY_HINT = re.compile(r"\b(sdn\.?\s*bhd|bhd|enterprise|trading|restaurant|cafe|"
                           r"store|mart|pharmacy|bookstore|hardware|s/b|plt|llp|inc|ltd|co)\b",
                           re.IGNORECASE)


@dataclass
class RuleResult:
    company: str | None = None
    date: str | None = None
    total: float | None = None
    reasons: list[str] = field(default_factory=list)   # why a field is missing/unsure
    total_candidates: list[float] = field(default_factory=list)


def extract_company(lines: list[str]) -> str | None:
    head = [l.strip() for l in lines[:8] if l and len(l.strip()) >= 3]
    # Prefer a line with a company-form hint (SDN BHD, Enterprise ...).
    for l in head:
        if _COMPANY_HINT.search(l) and not _COMPANY_SKIP.match(l):
            return norm_company(l)
    for l in head:
        if _COMPANY_SKIP.match(l):
            continue
        letters = sum(c.isalpha() for c in l)
        if letters >= 3 and letters / max(len(l), 1) > 0.5:
            return norm_company(l)
    return None


def extract_date(lines: list[str]) -> str | None:
    for l in lines:
        m = _DATE_HINT.search(l)
        if m:
            iso = norm_date(m.group(0), day_first=True)
            if iso and 2000 <= int(iso[:4]) <= 2035:
                return iso
    return None


def extract_total(lines: list[str]) -> tuple[float | None, list[float], str | None]:
    """Return (total, candidates, reason). Strategy: the money amount on the
    last line that carries a TOTAL keyword and no excluding keyword; if the
    keyword line has no amount, use the next line's amount. Fallback: the
    largest amount in the bottom half of the receipt."""
    candidates: list[float] = []
    keyword_hits: list[float] = []
    n = len(lines)
    for i, l in enumerate(lines):
        amounts = [norm_total(a) for a in _MONEY.findall(l)]
        amounts = [a for a in amounts if a is not None]
        if _TOTAL_KEYS.search(l) and not _TOTAL_EXCLUDE.search(l):
            if amounts:
                keyword_hits.append(amounts[-1])
            elif i + 1 < n:
                nxt = [norm_total(a) for a in _MONEY.findall(lines[i + 1])]
                nxt = [a for a in nxt if a is not None]
                if nxt:
                    keyword_hits.append(nxt[-1])
        if i >= n // 2:
            candidates.extend(amounts)
    if keyword_hits:
        # Several keyword lines (TOTAL, ROUNDED TOTAL, TOTAL PAYABLE): take the last.
        reason = None if len(set(keyword_hits)) == 1 else "total_multiple_keyword_amounts"
        return keyword_hits[-1], keyword_hits, reason
    if candidates:
        return max(candidates), candidates, "total_no_keyword_fallback_max"
    return None, [], "total_not_found"


def extract(lines: list[str]) -> RuleResult:
    r = RuleResult()
    r.company = extract_company(lines)
    if r.company is None:
        r.reasons.append("company_not_found")
    r.date = extract_date(lines)
    if r.date is None:
        r.reasons.append("date_not_found")
    r.total, r.total_candidates, reason = extract_total(lines)
    if reason:
        r.reasons.append(reason)
    return r
