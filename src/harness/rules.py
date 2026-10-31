"""rules.py - Deterministic field extraction from plain OCR text (tier 1).

Input: a list of text lines (top to bottom) as produced by a traditional OCR
engine. Output: company / date / total candidates plus the reasons the rules
could not decide. This is intentionally simple and transparent: the point of
the experiment is to measure how far cheap rules get and when to escalate.

Total strategy (v2, after inspecting 55 misses on the first 140 receipts):
  1. Score every line that carries a total-like label.
       strong: grand total, total payable, amount payable, total amount,
               net/nett total, total (incl...), total sales (inclusive...),
               rounded total, total due, amount due, total including gst
       medium: a bare "total" / "jumlah" / "amount"
     Lines are excluded when the label is a sub-total, a quantity, a tax or
     GST line, an "excluding" line, cash / change / tendered / paid amount,
     or a rounding adjustment.
  2. The amount is taken from the same line; if the label line has no amount,
     from the previous or the next line when that line is a lone amount (OCR
     engines often emit the right-aligned amount as its own line, sometimes
     before the label).
  3. Prefer the LAST strong hit; else the last medium hit; else the largest
     amount in the bottom half (reason: total_no_keyword_fallback_max).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .normalize import norm_company, norm_date, norm_total

_STRONG = re.compile(
    r"grand\s*total|total\s*(amt|amount)?\s*payable|amount\s*payable|total\s*amount|"
    r"ne?tt?\s*total|total\s*\(?\s*incl|total\s*sales?\s*\(?\s*incl|total\s*incl|"
    r"rounded\s*total|total\s*due|amount\s*due|total\s*\(?\s*including|total\s*\(?gst\s*incl|"
    r"total\s*inclusive|total\s*with\s*gst|total\s*after",
    re.IGNORECASE,
)
_MEDIUM = re.compile(r"\btotal\b|\bjumlah\b|\bamount\b", re.IGNORECASE)
_EXCLUDE = re.compile(
    r"sub\s*-?\s*total|subtotal|total\s*(qty|quantity|items?|savings?|discount|disc|pcs|unit)|"
    r"total\s*gst|gst\s*(amount|amt|total|summary)|total\s*tax|tax\s*(amount|total)|"
    r"excl|before|change|cash|tender|paid\s*amount|amount\s*paid|rounding|round\s*adj|"
    r"balance|credit|deposit|point|visa|master|card\b|total\s*ciy|total\s*city",
    re.IGNORECASE,
)
_MONEY = re.compile(r"(?<![\d.])-?\d{1,3}(?:,\d{3})*\.\d{2}(?![\d])|(?<![\d.])-?\d+\.\d{2}(?![\d])")
_LONE_AMOUNT = re.compile(r"^\s*(?:RM|MYR|\$)?\s*-?\d{1,3}(?:,\d{3})*\.\d{2}\s*$|^\s*(?:RM|MYR|\$)?\s*-?\d+\.\d{2}\s*$",
                          re.IGNORECASE)
_DATE_HINT = re.compile(
    r"\d{1,4}\s*[/\-.]\s*\d{1,2}\s*[/\-.]\s*\d{1,4}|\d{1,2}\s*[-/ ]?\s*[A-Za-z]{3,9}\s*[-/ ]?\s*\d{2,4}",
)
_COMPANY_SKIP = re.compile(
    r"^(tax\s*invoice|simplified|invoice|receipt|cash\s*bill|bill|welcome|thank|tel|fax|gst|"
    r"no\.?\s|www\.|http|\(?\d|[^A-Za-z]*$|lot\s|unit\s|jalan|jln|taman|kuala|selangor|johor|"
    r"penang|melaka|sdn\s*bhd\s*\(?\d)",
    re.IGNORECASE,
)
_COMPANY_HINT = re.compile(r"\b(sdn\.?\s*bhd|bhd|enterprise|trading|restaurant|restoran|cafe|"
                           r"store|mart|pharmacy|farmasi|bookstore|hardware|s/b|plt|llp|inc|ltd|co\b|"
                           r"holdings|resources|bakery|sales|services|supply|marketing)\b",
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
    # Prefer a line with a company-form hint (SDN BHD, Enterprise ...). When the
    # name wraps ("HOME MASTER HARDWARE &" / "ELECTRICAL", "SECURE PARKING" /
    # "CORPORATION S/B") join it with the previous header line.
    for i, l in enumerate(head):
        if _COMPANY_HINT.search(l) and not _COMPANY_SKIP.match(l):
            if i > 0 and not _COMPANY_SKIP.match(head[i - 1]) and not _COMPANY_HINT.search(head[i - 1]):
                prev = head[i - 1]
                letters = sum(c.isalpha() for c in prev)
                wrapped = prev.rstrip().endswith(("&", "AND", "and")) or (
                    letters >= 4 and letters / max(len(prev), 1) > 0.6 and len(l.split()) <= 3)
                if wrapped:
                    return norm_company(prev + " " + l)
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


def _amounts(line: str) -> list[float]:
    vals = [norm_total(a) for a in _MONEY.findall(line)]
    return [v for v in vals if v is not None]


def _amount_for_label(lines: list[str], i: int) -> float | None:
    """Amount on the label line, else a lone amount on the next or previous line."""
    own = _amounts(lines[i])
    if own:
        return own[-1]
    for j in (i + 1, i - 1):
        if 0 <= j < len(lines) and _LONE_AMOUNT.match(lines[j]):
            vals = _amounts(lines[j])
            if vals:
                return vals[-1]
    return None


def extract_total(lines: list[str]) -> tuple[float | None, list[float], str | None]:
    strong: list[float] = []
    medium: list[float] = []
    bottom: list[float] = []
    n = len(lines)
    for i, l in enumerate(lines):
        if i >= n // 2:
            bottom.extend(_amounts(l))
        if _EXCLUDE.search(l):
            continue
        if _STRONG.search(l):
            v = _amount_for_label(lines, i)
            if v is not None:
                strong.append(v)
        elif _MEDIUM.search(l):
            v = _amount_for_label(lines, i)
            if v is not None:
                medium.append(v)
    if strong:
        reason = None if len(set(strong)) == 1 else "total_multiple_strong_amounts"
        return strong[-1], strong, reason
    if medium:
        reason = None if len(set(medium)) == 1 else "total_multiple_keyword_amounts"
        return medium[-1], medium, reason
    if bottom:
        return max(bottom), bottom, "total_no_keyword_fallback_max"
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
