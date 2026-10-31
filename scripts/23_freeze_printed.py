"""23_freeze_printed.py - record the numbers printed on the submitted poster, once.

The poster PDF was submitted on 2026-10-31 and is not regenerated. This writes every number
report_numbers.numbers() gave the poster (the keys that existed before the after-poster additions)
to poster/printed_numbers.json with the PDF's SHA-256, so later pages can show "printed -> corrected"
for any number a fix changed. Refuses to overwrite an existing file.

    python scripts/23_freeze_printed.py
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from harness import report_numbers as RN  # noqa: E402

OUT = ROOT / "poster" / "printed_numbers.json"
PDF = ROOT / "poster" / "Park_Minwoo_MISM_ReceiptOCR.pdf"

if OUT.exists():
    sys.exit(f"{OUT.relative_to(ROOT)} exists; the printed numbers are frozen")
V = RN.numbers()
after = set(RN._after_poster({p["policy"]: p for p in RN._j("results/harness/policies.json")},
                             {p["policy"]: p for p in RN._j("results_wild/harness/policies.json")}))
printed = {k: v for k, v in V.items() if k not in after}
OUT.write_text(json.dumps({"pdf": PDF.name, "pdf_sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
                           "frozen": "2026-10-31", "numbers": printed}, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"wrote {OUT.relative_to(ROOT)}: {len(printed)} numbers")
