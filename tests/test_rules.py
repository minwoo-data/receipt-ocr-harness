import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from harness import rules  # noqa: E402

RECEIPT = [
    "UNIHAKKA INTERNATIONAL SDN BHD",
    "13 May 2018 18:26",
    "(867388-U)",
    "12,Jalan Tampoi 7/4,Kawasan Perindustrian",
    "TAX INVOICE",
    "Item Qty",
    "SR 1 Fish + 3 Vege $8.10 1 $8.10",
    "SR Add Vegetable $0.60 1 $0.60",
    "Total Amount: $8.70",
    "GST @6%: $0.49",
    "Nett Total: $8.70",
    "CASH $8.70",
    "Change $0.00",
]


def test_rules_extract_happy_path():
    r = rules.extract(RECEIPT)
    assert r.company == "UNIHAKKA INTERNATIONAL SDN BHD"
    assert r.date == "2018-05-13"
    assert r.total == 8.7
    assert r.reasons == []


def test_rules_ignore_subtotal_and_change_lines():
    lines = ["SHOP A", "01/02/2019", "SUBTOTAL 10.00", "GST 0.60", "TOTAL 10.60", "CASH 20.00", "CHANGE 9.40"]
    r = rules.extract(lines)
    assert r.total == 10.6


def test_rules_report_missing_fields():
    r = rules.extract(["12345", "no useful text here"])
    assert r.total is None
    assert "total_not_found" in r.reasons
    assert "date_not_found" in r.reasons


def test_rules_fallback_when_no_keyword():
    lines = ["SHOP B", "05/05/2019", "Item 3.00", "Item 4.50", "7.50"]
    r = rules.extract(lines)
    assert r.total == 7.5
    assert "total_no_keyword_fallback_max" in r.reasons
