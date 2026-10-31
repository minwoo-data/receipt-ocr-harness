import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from harness import verify  # noqa: E402

TODAY = date(2026, 10, 31)
OCR = ["PASIR EMAS HARDWARE SDN BHD", "23/06/18", "ITEM 36.00", "TOTAL 36.00", "CASH 50.00", "CHANGE 14.00"]


def rec(data, is_safe=True, warnings=None):
    return {"data": data, "sanitizer": {"is_safe": is_safe, "warnings": warnings or []}}


def names(flags):
    return sorted(f.name for f in flags)


def test_clean_record_has_no_flags():
    data = {"vendor": "PASIR EMAS HARDWARE SDN BHD", "date": "2018-06-23", "subtotal": 36.0,
            "tax": 0.0, "tip": None, "discount": None, "total": 36.0, "confidence": 0.1}
    assert verify.verify(rec(data), OCR, today=TODAY) == []     # low self-confidence is irrelevant


def test_arithmetic_mismatch_flagged_and_absent_is_not_zero():
    bad = {"vendor": "X", "date": "2018-06-23", "subtotal": 30.0, "tax": 1.8, "tip": None, "discount": None, "total": 36.0}
    assert "G_ARITH" in names(verify.check_arithmetic(bad))
    ok_absent = {"subtotal": 36.0, "tax": None, "tip": None, "discount": None, "total": 36.0}
    assert verify.check_arithmetic(ok_absent) == []
    tax_inclusive = {"subtotal": 36.0, "tax": 2.16, "tip": None, "discount": None, "total": 36.0}
    assert verify.check_arithmetic(tax_inclusive) == []
    within_tolerance = {"subtotal": 10.0, "tax": 0.6, "tip": 0, "discount": 0, "total": 10.61}
    assert verify.check_arithmetic(within_tolerance) == []


def test_date_gate():
    assert names(verify.check_date({"date": "2027-03-05"}, today=TODAY)) == ["G_DATE"]
    assert names(verify.check_date({"date": "1998-01-01"}, today=TODAY)) == ["G_DATE"]
    assert names(verify.check_date({"date": "not a date"}, today=TODAY)) == ["G_DATE"]
    assert verify.check_date({"date": "23/06/18"}, today=TODAY) == []


def test_two_reader_agreement():
    hallucinated_total = {"vendor": "X", "date": "2018-06-23", "total": 0.0}
    flags = names(verify.check_agreement({"total": 99.99, "date": "2018-06-23"}, OCR))
    assert "G_AGREE_TOTAL" in flags
    assert verify.check_agreement({"total": 36.0, "date": "2018-06-23"}, OCR) == []
    assert "G_AGREE_DATE" in names(verify.check_agreement({"total": 36.0, "date": "2011-01-01"}, OCR))
    assert verify.check_agreement(hallucinated_total, None) == []   # no OCR text, no opinion


def test_sanitizer_and_missing_and_range():
    assert names(verify.check_sanitizer(rec({}, is_safe=False, warnings=["Injection pattern in 'notes'"]))) == ["G_SANITIZER"]
    assert "G_MISSING" in names(verify.check_missing({"vendor": None, "date": "2018-06-23", "total": 1.0}))
    assert "G_RANGE" in names(verify.check_range({"total": -5.0}))
    assert "G_RANGE" in names(verify.check_range({"total": 10.0, "tax": -1.0}))
    assert verify.verify({"data": None, "sanitizer": {}}, OCR, today=TODAY)[0].name == "G_MISSING"


def test_suspect_field_priority():
    flags = [verify.Flag("G_DATE", "date_future"), verify.Flag("G_ARITH", "x")]
    assert verify.suspect_field(flags) == "total"
    assert verify.suspect_field([verify.Flag("G_AGREE_DATE", "x")]) == "date"
    assert verify.suspect_field([]) is None
