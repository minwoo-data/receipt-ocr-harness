"""verify.py - Code-level checks on a model's receipt extraction.

None of these checks consult the model's own confidence and none use ground
truth. They are what production code can run on every receipt:

  G_SANITIZER   output failed the injection / type / range sanitizer
  G_MISSING     a required field (vendor, date, total) is null
  G_ARITH       subtotal + tax + tip + discount != total beyond tolerance,
                absent fields excluded (absent is not zero), with a
                tax-inclusive alternative accepted (KR/JP/EU/MY VAT inside total)
  G_DATE        date unparseable, in the future, or implausibly old
  G_RANGE       total <= 0 or above a ceiling, negative tax/tip
  G_AGREE_TOTAL the model's total does not appear in the independent OCR text
  G_AGREE_DATE  no token of the model's date appears in the independent OCR text

Optional gate (verify(..., gates=("total_label",)); designed on SROIE 300 only,
frozen before WildReceipt was scored):

  G_TOTAL_TENDER  the model's total appears in the OCR text only on payment
                  lines (cash, change, accepted, tendered, paid, card): the
                  amount handed over, not the amount owed
  G_TOTAL_ROUNDED the model's total is not a multiple of 0.05 and a total /
                  payable line prints an amount within 2 cents that is: the
                  pre-rounding figure instead of the rounded payable

Each check returns a Flag(name, detail). An empty flag list is the only state
in which auto-accept is allowed. Model confidence is carried through for
logging but never consulted here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .normalize import date_plausible, norm_date, norm_total

TOLERANCE = 0.05      # production used 0.02 (USD); MYR receipts round to the nearest 0.05
TOTAL_CEILING = 100_000.0


@dataclass(frozen=True)
class Flag:
    name: str
    detail: str


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def check_sanitizer(record: dict) -> list[Flag]:
    san = record.get("sanitizer") or {}
    if san.get("is_safe") is False:
        return [Flag("G_SANITIZER", "; ".join(san.get("warnings") or [])[:200])]
    return []


def check_missing(data: dict) -> list[Flag]:
    flags = []
    for key in ("vendor", "date", "total"):
        if data.get(key) in (None, "", 0) and not (key == "total" and _num(data.get(key)) not in (None, 0.0)):
            if key == "total" and _num(data.get(key)) is not None and _num(data.get(key)) != 0.0:
                continue
            flags.append(Flag("G_MISSING", key))
    return flags


def check_arithmetic(data: dict, tolerance: float = TOLERANCE) -> list[Flag]:
    """Absent (null) fields are excluded from the equation. Zero is a value."""
    subtotal, tax, tip, disc, total = (_num(data.get(k)) for k in ("subtotal", "tax", "tip", "discount", "total"))
    if total is None or subtotal is None:
        return []                      # nothing to cross-check without both anchors
    def close(a: float, b: float) -> bool:
        return round(abs(a - b), 2) <= tolerance

    parts = [v for v in (subtotal, tax, tip, disc) if v is not None]
    additive = round(sum(parts), 2)
    if close(additive, total):
        return []
    # Tax-inclusive receipts print tax inside the total: subtotal + tip + discount == total.
    inclusive = round(sum(v for v in (subtotal, tip, disc) if v is not None), 2)
    if tax is not None and tax > 0 and close(inclusive, total):
        return []
    # Discount already netted into the printed subtotal (common on pharmacy /
    # retail slips): subtotal (+ tax) == total with the discount line ignored.
    if disc is not None and disc != 0:
        netted = round(sum(v for v in (subtotal, tax, tip) if v is not None), 2)
        if close(netted, total) or close(round(sum(v for v in (subtotal, tip) if v is not None), 2), total):
            return []
    return [Flag("G_ARITH", f"subtotal+tax+tip+discount={additive} vs total={total}")]


def check_date(data: dict, today: date | None = None, min_year: int | None = None) -> list[Flag]:
    """Plausibility window: not after `today`, not before `min_year`. The
    window is set per dataset era (SROIE receipts are from 2016-2019; the
    synthetic set is dated 2026), so an ancient or future date is judged
    relative to when the receipts were issued, not to the wall clock."""
    iso = norm_date(data.get("date"), day_first=True)
    today = today or date.today()
    ok, reason = date_plausible(iso, today=today, min_year=min_year if min_year is not None else today.year - 3)
    return [] if ok else [Flag("G_DATE", reason or "date_invalid")]


def check_range(data: dict) -> list[Flag]:
    flags = []
    total = _num(data.get("total"))
    if total is not None and (total <= 0 or total > TOTAL_CEILING):
        flags.append(Flag("G_RANGE", f"total={total}"))
    for k in ("tax", "tip", "subtotal"):
        v = _num(data.get(k))
        if v is not None and v < 0:
            flags.append(Flag("G_RANGE", f"{k}={v}"))
    return flags


_NUM_TOKEN = re.compile(r"\d[\d,]*\.?\d*")


def _ocr_numbers(ocr_lines: list[str]) -> set[str]:
    nums = set()
    for line in ocr_lines:
        for tok in _NUM_TOKEN.findall(line):
            tok = tok.replace(",", "")
            try:
                nums.add(f"{float(tok):.2f}")
            except ValueError:
                continue
    return nums


def check_agreement(data: dict, ocr_lines: list[str] | None) -> list[Flag]:
    """Two independent readers: the LLM's total must be a number the OCR engine
    also saw, and at least one of the date's day/month/year tokens must appear
    in the OCR text. Weak on purpose: it catches hallucinated totals, not
    one-digit misreads shared by both readers."""
    if not ocr_lines:
        return []
    flags = []
    total = _num(data.get("total"))
    if total is not None:
        if f"{total:.2f}" not in _ocr_numbers(ocr_lines):
            flags.append(Flag("G_AGREE_TOTAL", f"{total:.2f} not in OCR text"))
    iso = norm_date(data.get("date"), day_first=True)
    if iso:
        candidates = ocr_date_candidates(ocr_lines)
        # Abstain when the OCR engine saw no date at all: a disagreement needs
        # two opinions. Flag only when OCR read a date and it differs.
        if candidates and iso not in candidates:
            flags.append(Flag("G_AGREE_DATE", f"{iso} vs OCR {sorted(candidates)[:3]}"))
    return flags


_DATE_NUMERIC = re.compile(r"(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4}|\d{2})")
_DATE_TEXTUAL = re.compile(r"(\d{1,2})\s*[-/ ]?\s*([A-Za-z]{3,9})\s*[-/ ]?\s*(\d{4}|\d{2})(?!\d)")


def ocr_date_candidates(ocr_lines: list[str]) -> set[str]:
    """Every ISO date a traditional OCR engine's text could be read as.
    Receipts glue the time onto the date ("23/06/1812:46:33PM"), so a 4-digit
    year outside 2000-2035 is re-read as a 2-digit year."""
    found: set[str] = set()
    for line in ocr_lines:
        for a, b, c in _DATE_NUMERIC.findall(line):
            years = [c] if len(c) == 2 else ([c] if 2000 <= int(c) <= 2035 else [c[:2]])
            for y in years:
                for day_first in (True, False):
                    iso = norm_date(f"{a}/{b}/{y}", day_first=day_first)
                    if iso and 2000 <= int(iso[:4]) <= 2035:
                        found.add(iso)
        for a, mon, c in _DATE_TEXTUAL.findall(line):
            iso = norm_date(f"{a} {mon} {c}")
            if iso and 2000 <= int(iso[:4]) <= 2035:
                found.add(iso)
    return found


_TENDER_WORDS = ("cash", "change", "tender", "accepted", "paid", "received", "refund", "visa", "master", "amex", "debit", "card")
_FINAL_WORDS = ("total", "totai", "payable", "amountdue", "amtdue", "balancedue", "grand", "nett", "rounded", "afteradj")
_NOT_FINAL_WORDS = ("subtotal", "subtot", "excl", "exclud", "before")


def _label(line: str) -> str:
    s = re.sub(r"[^a-z]", "", line.lower())
    return s.replace("cashier", "")             # "Cashier: 01" is a person, not a payment


def _is_tender(line: str) -> bool:
    s = _label(line)
    return any(w in s for w in _TENDER_WORDS)


def _is_final(line: str) -> bool:
    s = _label(line)
    return any(w in s for w in _FINAL_WORDS) and not any(w in s for w in _NOT_FINAL_WORDS) and not _is_tender(line)


def _cents(line: str) -> set[int]:
    out = set()
    for tok in _NUM_TOKEN.findall(line):
        try:
            out.add(round(float(tok.replace(",", "")) * 100))
        except ValueError:
            continue
    return out


def check_total_label(data: dict, ocr_lines: list[str] | None) -> list[Flag]:
    """Which printed amount did the model pick? Uses only the OCR text and the
    line labels, never the answer key. Abstains without OCR text or a total."""
    total = _num(data.get("total"))
    if not ocr_lines or total is None or total <= 0:
        return []
    t = round(total * 100)
    flags = []
    carrying = [l for l in ocr_lines if t in _cents(l)]
    if carrying and all(_is_tender(l) for l in carrying) and any(_cents(l) - {t} for l in ocr_lines if not _is_tender(l)):
        flags.append(Flag("G_TOTAL_TENDER", f"{total:.2f} printed only on payment lines"))
    if t % 5 != 0:
        near = sorted({c for l in ocr_lines if _is_final(l) for c in _cents(l) if c != t and c % 5 == 0 and abs(c - t) <= 2})
        if near:
            flags.append(Flag("G_TOTAL_ROUNDED", f"{total:.2f} vs rounded {near[0] / 100:.2f} on a total line"))
    return flags


def verify(record: dict, ocr_lines: list[str] | None = None, today: date | None = None,
           min_year: int | None = None, gates: tuple[str, ...] = ()) -> list[Flag]:
    """All checks on one VLM record (as written by engines.vlm). Returns the
    flags; empty means every code check passed. `gates` switches on optional
    checks by name ("total_label")."""
    data = record.get("data")
    if not isinstance(data, dict):
        return [Flag("G_MISSING", "no_parseable_json")]
    flags: list[Flag] = []
    flags += check_sanitizer(record)
    flags += check_missing(data)
    flags += check_arithmetic(data)
    flags += check_date(data, today=today, min_year=min_year)
    flags += check_range(data)
    flags += check_agreement(data, ocr_lines)
    if "total_label" in gates:
        flags += check_total_label(data, ocr_lines)
    return flags


def suspect_field(flags: list[Flag]) -> str | None:
    """Which field a targeted retry should focus on, by priority."""
    names = {f.name for f in flags}
    if "G_ARITH" in names or "G_AGREE_TOTAL" in names or any(f.name == "G_MISSING" and f.detail == "total" for f in flags):
        return "total"
    if "G_DATE" in names or "G_AGREE_DATE" in names or any(f.name == "G_MISSING" and f.detail == "date" for f in flags):
        return "date"
    if any(f.name == "G_MISSING" and f.detail == "vendor" for f in flags):
        return "vendor"
    return None
