"""normalize.py - Canonical forms for the three scored fields.

Scoring is exact match AFTER normalization, done by code (never by a model):
  company -> uppercase, punctuation stripped, whitespace collapsed
  date    -> ISO YYYY-MM-DD or None (SROIE receipts are Malaysian: day-first)
  total   -> float rounded to 2 dp or None

The same functions normalize ground truth and every engine's output, so a
difference in formatting never counts as an OCR error.
"""

from __future__ import annotations

import re
from datetime import date

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_COMPANY_DROP = re.compile(r"[^A-Z0-9 ]+")
_PARENS = re.compile(r"\([^)]*\)|（[^）]*）")
_REG_CODE = re.compile(r"\b\d{5,}\s*-?\s*[A-Z]?\b")      # Malaysian company registration numbers
_SPACES = re.compile(r"\s+")


def norm_company(value) -> str | None:
    """Uppercase, parentheses and registration codes removed, punctuation to
    spaces, whitespace collapsed. Compare with company_key() so that OCR word
    merging ("SDNBHD" vs "SDN BHD") is not counted as a reading error."""
    if value is None:
        return None
    s = str(value).upper()
    s = _PARENS.sub(" ", s)
    s = _COMPANY_DROP.sub(" ", s)
    s = _REG_CODE.sub(" ", s)
    s = _SPACES.sub(" ", s).strip()
    return s or None


def company_key(value) -> str | None:
    s = norm_company(value)
    return s.replace(" ", "") if s else None


def _year(y: str) -> int:
    n = int(y)
    if len(y) == 2:
        return 2000 + n if n < 70 else 1900 + n
    return n


def norm_date(value, day_first: bool = True) -> str | None:
    """Return ISO date or None. ``day_first`` resolves 05/03/2018 style
    ambiguity (True for SROIE / most non-US receipts)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s.replace(",", " ")

    # 1. numeric with separators: d/m/y, m/d/y, y/m/d (2- or 4-digit year)
    m = re.search(r"(\d{1,4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,4})", s)
    if m:
        a, b, c = m.groups()
        try:
            if len(a) == 4:                       # y/m/d
                return date(int(a), int(b), int(c)).isoformat()
            if day_first:
                d, mth, y = int(a), int(b), _year(c)
            else:
                mth, d, y = int(a), int(b), _year(c)
            try:
                return date(y, mth, d).isoformat()
            except ValueError:
                # swap if the chosen order is impossible (e.g. 13 as month)
                return date(y, d, mth).isoformat()
        except ValueError:
            pass

    # 2. textual month: 25 DEC 2018 / DEC 25 2018 / 25-Dec-18
    m = re.search(r"(\d{1,2})\s*[-/ ]?\s*([A-Za-z]{3,9})\s*[-/ ]?\s*(\d{2,4})", s)
    if m:
        d, mon, y = m.groups()
        mth = _MONTHS.get(mon.lower()[:4]) or _MONTHS.get(mon.lower()[:3])
        if mth:
            try:
                return date(_year(y), mth, int(d)).isoformat()
            except ValueError:
                pass
    m = re.search(r"([A-Za-z]{3,9})\s*[-/ ]?\s*(\d{1,2})\s*[-/ ]?\s*(\d{2,4})", s)
    if m:
        mon, d, y = m.groups()
        mth = _MONTHS.get(mon.lower()[:4]) or _MONTHS.get(mon.lower()[:3])
        if mth:
            try:
                return date(_year(y), mth, int(d)).isoformat()
            except ValueError:
                pass

    # 3. compact 8 digits: 20181225 or 25122018
    m = re.search(r"(?<!\d)(\d{8})(?!\d)", s)
    if m:
        t = m.group(1)
        for y, mth, d in ((t[:4], t[4:6], t[6:]), (t[4:], t[2:4], t[:2])):
            try:
                return date(int(y), int(mth), int(d)).isoformat()
            except ValueError:
                continue
    return None


_AMOUNT = re.compile(r"-?\d{1,3}(?:[,\s]\d{3})*(?:\.\d{1,2})?|-?\d+(?:\.\d{1,2})?")


def norm_total(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    s = str(value).strip().replace("RM", "").replace("$", "")
    m = _AMOUNT.search(s)
    if not m:
        return None
    num = m.group(0).replace(",", "").replace(" ", "")
    try:
        return round(float(num), 2)
    except ValueError:
        return None


def date_plausible(iso: str | None, today: date | None = None,
                   min_year: int = 2000) -> tuple[bool, str | None]:
    """Code-level date sanity: parseable, not in the future, not ancient.
    Returns (ok, reason)."""
    if not iso:
        return False, "date_unparsed"
    y, m, d = (int(x) for x in iso.split("-"))
    dt = date(y, m, d)
    today = today or date.today()
    if dt > today:
        return False, "date_future"
    if y < min_year:
        return False, "date_too_old"
    return True, None
