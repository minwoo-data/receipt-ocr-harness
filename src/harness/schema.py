"""schema.py - ONE extraction prompt and ONE JSON schema shared by every
vision-LLM tier (local Qwen3-VL and cloud Gemini / Claude).

Keeping the prompt identical across tiers is what makes the comparison fair:
the only variable is the model. The injection-defense prefix comes from the
vendored boda sanitizer so the production habit carries over unchanged.
"""

from __future__ import annotations

from .vendor_boda.sanitizer import get_injection_defense_prompt

FIELDS = ("vendor", "date", "subtotal", "tax", "tip", "discount", "total",
          "currency", "confidence", "notes")

RECEIPT_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "vendor": {"type": ["string", "null"], "description": "Official business name as printed"},
        "date": {"type": ["string", "null"], "description": "Transaction date in ISO YYYY-MM-DD"},
        "subtotal": {"type": ["number", "null"]},
        "tax": {"type": ["number", "null"]},
        "tip": {"type": ["number", "null"]},
        "discount": {"type": ["number", "null"], "description": "Negative for coupons/credits"},
        "total": {"type": ["number", "null"], "description": "Amount charged, as printed"},
        "currency": {"type": ["string", "null"], "description": "ISO 4217 code such as MYR, USD"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "notes": {"type": ["string", "null"]},
    },
    "required": ["vendor", "date", "subtotal", "tax", "tip", "discount", "total",
                 "currency", "confidence", "notes"],
}


def extraction_prompt() -> str:
    return (
        get_injection_defense_prompt()
        + "Read this receipt image carefully and extract the fields below as one JSON object.\n\n"
        "RULES:\n"
        "1. Read every visible line before answering. Do NOT invent text you cannot see.\n"
        "2. date: ISO format YYYY-MM-DD. Receipts outside the US usually print day first "
        "(DD/MM/YYYY); use the printed order and the country context to decide. "
        "If the year has 2 digits, expand it (18 -> 2018).\n"
        "3. All amounts are plain numbers with no currency symbol.\n"
        "4. total is the amount CHARGED as printed. Never report Cash Tendered, Change, "
        "or Amount Received as the total. Prefer the line labelled Total / Grand Total / "
        "Total Payable / Rounded Total (use the rounded total when both are printed).\n"
        "5. If a field is not printed on the receipt, return null. Do NOT invent 0 to make "
        "the arithmetic balance.\n"
        "6. discount is negative for coupons, credits and vouchers.\n"
        "7. vendor: the official business name as printed at the top, not the address.\n"
        "8. confidence: your own estimate in [0, 1] of how readable the receipt was. "
        "Compute it; do not default to 0.95. It will be logged, not trusted.\n"
        "9. notes: one short sentence on anything unclear, else null.\n\n"
        "Return ONLY the JSON object, no markdown, no explanation."
    )


def retry_prompt_blind(field: str) -> str:
    """Blind re-read: names the suspect field, shows NO previous values."""
    return (
        extraction_prompt()
        + f"\n\nA verification check flagged the field '{field}' from a previous read. "
        f"Re-read the receipt from scratch and pay special attention to '{field}'. "
        "Do not assume the previous value was right or wrong."
    )


def retry_prompt_guided(field: str, previous: dict, reason: str) -> str:
    """Guided re-read (production style): shows previous values and the
    failed check, but never a target value for the suspect field."""
    prev = {k: previous.get(k) for k in ("vendor", "date", "subtotal", "tax", "tip", "discount", "total")}
    return (
        extraction_prompt()
        + f"\n\nYour previous extraction was {prev}. A verification check failed: {reason}. "
        f"Re-read the PRINTED values carefully, especially '{field}'. Keep every amount exactly "
        "as printed; if a field is not on the receipt leave it null rather than inventing a value."
    )
