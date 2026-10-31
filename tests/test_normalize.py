import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from harness.normalize import date_plausible, norm_company, norm_date, norm_total  # noqa: E402


def test_company_strips_punctuation_and_case():
    assert norm_company("Lavender Confectionery & Bakery S/B") == "LAVENDER CONFECTIONERY BAKERY S B"
    assert norm_company("  PASIR  EMAS  ") == "PASIR EMAS"
    assert norm_company(None) is None


def test_date_day_first_numeric():
    assert norm_date("17/06/2018") == "2018-06-17"
    assert norm_date("23/06/18") == "2018-06-23"
    assert norm_date("2018-06-17") == "2018-06-17"
    assert norm_date("06/17/2018") == "2018-06-17"      # impossible as day-first, swapped


def test_date_textual_and_compact():
    assert norm_date("10 MAR 2018") == "2018-03-10"
    assert norm_date("13 May 2018 18:26") == "2018-05-13"
    assert norm_date("Mar 10, 2018") == "2018-03-10"
    assert norm_date("20180310") == "2018-03-10"
    assert norm_date("garbage") is None
    assert norm_date("") is None


def test_total_formats():
    assert norm_total("26.50") == 26.5
    assert norm_total("RM 1,234.50") == 1234.5
    assert norm_total("$8.70") == 8.7
    assert norm_total(36) == 36.0
    assert norm_total("") is None


def test_date_plausible():
    today = date(2026, 10, 31)
    assert date_plausible("2018-06-17", today) == (True, None)
    assert date_plausible("2027-03-05", today) == (False, "date_future")
    assert date_plausible("1998-01-01", today) == (False, "date_too_old")
    assert date_plausible(None, today) == (False, "date_unparsed")
