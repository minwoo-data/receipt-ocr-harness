# -*- coding: utf-8 -*-
"""
processor.py - Receipt Processing Engine (multi-provider)
=========================================================
Analyzes receipt images and returns structured JSON data.

Engine:
- Multi-provider OCR with a configurable fallback chain (Gemini 2.5 Flash
  primary, Claude fallback) — see providers.py.
- Per-provider circuit breaker: a provider outage skips that provider for a
  cooldown window instead of burning the full retry budget on every upload.
- Prompt-injection defense + response sanitizing — see sanitizer.py.
- Image preprocessing (resize, EXIF rotation, PDF rendering).
- Data normalization (dates, amounts, categories), amount cross-validation
  (subtotal + tax + tip = total), confidence scoring, and review flagging.
"""

import base64
import io
import json
import logging
import os
import re
import sys
from datetime import datetime

from PIL import Image

import providers
from sanitizer import get_injection_defense_prompt, validate_ai_response

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)
_log_file_handler = logging.FileHandler("logs/processing.log", encoding="utf-8")
_log_stream_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[_log_file_handler, _log_stream_handler],
)
logger = logging.getLogger("ReceiptProcessor")


class ReceiptProcessor:
    """Processes receipt images via a provider fallback chain.

    Config (config.json):
      ocr.provider_priority : ["gemini", "claude"]
      ocr.max_retries / ocr.retry_delay
      ocr.circuit.open_after_consecutive / ocr.circuit.cooldown_seconds
      gemini.{api_key, model, max_tokens, temperature}
      claude.{api_key, model, max_tokens, temperature}
    API keys may instead come from GEMINI_API_KEY / ANTHROPIC_API_KEY env vars.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self, config: dict):
        self.config = config
        ocr_cfg = config.get("ocr", {})

        self.max_retries = int(ocr_cfg.get("max_retries", self.MAX_RETRIES))
        self.retry_delay = int(ocr_cfg.get("retry_delay", self.RETRY_DELAY))
        circuit_cfg = ocr_cfg.get("circuit", {})
        open_after = int(circuit_cfg.get("open_after_consecutive", 3))
        cooldown = int(circuit_cfg.get("cooldown_seconds", 60))

        self.categories = config["categories"]
        self.confidence_threshold = config["validation"]["confidence_threshold"]
        self.review_threshold = config["validation"]["flag_for_review_threshold"]

        # Resolve providers in priority order; keep only those with a key.
        priority = ocr_cfg.get("provider_priority", ["gemini", "claude"])
        self.providers = []   # list of provider-name strings, in order
        self._gemini_client = None
        self._gemini_cfg = {}
        self._claude_client = None
        self._claude_cfg = {}
        self._circuits = {}

        for name in priority:
            if name == "gemini":
                key = (config.get("gemini", {}).get("api_key")
                       or os.environ.get("GEMINI_API_KEY", ""))
                if not key or key.startswith("YOUR_"):
                    logger.warning("Gemini configured but no API key — skipping")
                    continue
                self._gemini_cfg = {
                    "model": config.get("gemini", {}).get("model", "gemini-2.5-flash"),
                    "max_tokens": config.get("gemini", {}).get("max_tokens", 1500),
                    "temperature": config.get("gemini", {}).get("temperature", 0.0),
                }
                try:
                    self._gemini_client = providers.build_gemini_client(key)
                except Exception as e:  # noqa: BLE001 - missing SDK / bad key
                    logger.warning("Gemini client init failed (%s) — skipping",
                                   providers.redact_provider_error(e))
                    continue
                self.providers.append("gemini")
                self._circuits["gemini"] = providers.CircuitBreaker(open_after, cooldown)

            elif name == "claude":
                key = (config.get("claude", {}).get("api_key")
                       or os.environ.get("ANTHROPIC_API_KEY", ""))
                if not key or key.startswith("YOUR_"):
                    logger.warning("Claude configured but no API key — skipping")
                    continue
                self._claude_cfg = {
                    "model": config.get("claude", {}).get("model",
                                                          "claude-haiku-4-5-20251001"),
                    "max_tokens": config.get("claude", {}).get("max_tokens", 1500),
                    "temperature": config.get("claude", {}).get("temperature", 0.0),
                }
                try:
                    import anthropic
                    self._claude_client = anthropic.Anthropic(
                        api_key=key, timeout=60.0, max_retries=0)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Claude client init failed (%s) — skipping",
                                   providers.redact_provider_error(e))
                    continue
                self.providers.append("claude")
                self._circuits["claude"] = providers.CircuitBreaker(open_after, cooldown)

        if not self.providers:
            raise ValueError(
                "No OCR provider available. Set gemini.api_key / claude.api_key "
                "in config.json (or GEMINI_API_KEY / ANTHROPIC_API_KEY env vars)."
            )

        logger.info("ReceiptProcessor initialized (providers: %s)",
                    ", ".join(self.providers))

    # ======================================================================
    # Main entry point
    # ======================================================================
    def process_receipt(self, image_path: str) -> dict:
        """Analyze a receipt image and return structured data.

        Returns dict: success, data, confidence, needs_review, issue, error.
        """
        logger.info("Processing: %s", os.path.basename(image_path))
        try:
            image_data, media_type = self._load_and_prepare_image(image_path)
            if image_data is None:
                return self._error_result("Failed to read image file")

            raw_response = self._call_providers(image_data, media_type)
            if raw_response is None:
                return self._error_result("All OCR providers failed")

            data = providers.parse_response(raw_response)
            if data is None:
                return self._error_result("Failed to parse OCR response")
            if isinstance(data, list):  # single-page input: take first object
                data = data[0] if data and isinstance(data[0], dict) else None
                if data is None:
                    return self._error_result("OCR response had no object")

            # Prompt-injection defense / response sanitizing.
            is_safe, data, sec_warnings = validate_ai_response(data)
            if not is_safe:
                logger.warning("Sanitizer flagged response: %s", sec_warnings)

            data = self._normalize_data(data)
            data = self._cross_validate_amounts(data)
            is_valid, errors = self._validate_data(data)

            if not is_safe:
                errors.append("Security filter modified suspicious content")

            if not is_valid or not is_safe:
                return {
                    "success": True,
                    "data": data,
                    "confidence": data.get("confidence", 0.5),
                    "needs_review": True,
                    "issue": " / ".join(errors) if errors else "Review needed",
                    "error": None,
                }

            confidence = data.get("confidence", 0.0)
            needs_review = confidence < self.review_threshold
            issue = self._identify_issues(data, confidence) if needs_review else None

            logger.info("Done: %s | $%.2f | %s | confidence %.0f%%",
                        data.get("vendor", "?"), data.get("total", 0),
                        data.get("category", "?"), confidence * 100)

            return {
                "success": True,
                "data": data,
                "confidence": confidence,
                "needs_review": needs_review,
                "issue": issue,
                "error": None,
            }
        except Exception as e:  # noqa: BLE001
            logger.error("Unexpected error: %s", str(e), exc_info=True)
            return self._error_result(str(e))

    # ======================================================================
    # Provider fallback chain
    # ======================================================================
    def _call_providers(self, data_b64: str, media_type: str):
        """Try each provider in priority order, skipping open circuits."""
        prompt = self._build_extraction_prompt()
        page_payloads = [(data_b64, media_type)]

        open_count = 0
        for name in self.providers:
            circuit = self._circuits[name]
            if circuit.is_open():
                logger.warning("Skipping %s — circuit open", name)
                open_count += 1
                continue

            if name == "gemini":
                text = providers.call_gemini_with_retry(
                    self._gemini_client, self._gemini_cfg, page_payloads,
                    prompt, self.max_retries, self.retry_delay)
            else:  # claude
                text = providers.call_claude_with_retry(
                    self._claude_client, self._claude_cfg, page_payloads,
                    prompt, self.max_retries, self.retry_delay)

            if text:
                circuit.record_success()
                logger.info("OCR succeeded via %s", name)
                return text
            circuit.record_failure()
            logger.warning("%s returned no result — trying next provider", name)

        if open_count == len(self.providers):
            logger.error("All provider circuits open — OCR temporarily unavailable")
        return None

    # ======================================================================
    # Image loading
    # ======================================================================
    def _load_and_prepare_image(self, image_path: str):
        """Load image -> (base64, media_type). PDF via PyMuPDF/pdf2image/raw."""
        try:
            ext = os.path.splitext(image_path)[1].lower()
            if ext == ".pdf":
                return self._load_pdf(image_path)
            with Image.open(image_path) as img:
                try:
                    from PIL import ImageOps
                    img = ImageOps.exif_transpose(img)
                except Exception:
                    pass
                logger.info("Image loaded: %s (%dx%d, %s)",
                            os.path.basename(image_path), img.width, img.height,
                            img.mode)
                return self._pil_to_base64(img)
        except Exception as e:  # noqa: BLE001
            logger.error("Image load failed: %s", str(e))
            return None, None

    def _pil_to_base64(self, img: Image.Image):
        """Convert a PIL image to base64 JPEG (flatten alpha, resize)."""
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if "A" in img.mode:
                bg.paste(img, mask=img.split()[-1])
            else:
                bg.paste(img)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        max_dim = 2048
        if max(img.width, img.height) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            logger.info("Resized to: %dx%d", img.width, img.height)
        if min(img.width, img.height) < 200:
            logger.warning("Image is very small (%dx%d)", img.width, img.height)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return b64, "image/jpeg"

    def _load_pdf(self, pdf_path: str):
        """Render the first PDF page; fall back to raw PDF bytes."""
        logger.info("Loading PDF: %s", os.path.basename(pdf_path))
        try:
            import fitz
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                logger.error("PDF has no pages")
                return None, None
            page = doc[0]
            mat = fitz.Matrix(200 / 72, 200 / 72)  # 200 DPI
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()
            logger.info("PDF converted via PyMuPDF: %dx%d", img.width, img.height)
            return self._pil_to_base64(img)
        except ImportError:
            logger.info("PyMuPDF not installed, trying alternatives")
        except Exception as e:  # noqa: BLE001
            logger.warning("PyMuPDF failed: %s", str(e))

        try:
            from pdf2image import convert_from_path
            images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=200)
            if images:
                return self._pil_to_base64(images[0])
        except ImportError:
            logger.info("pdf2image not installed, sending raw PDF")
        except Exception as e:  # noqa: BLE001
            logger.warning("pdf2image failed: %s", str(e))

        try:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            b64 = base64.b64encode(pdf_bytes).decode("ascii")
            logger.info("Sending raw PDF (%d bytes)", len(pdf_bytes))
            return b64, "application/pdf"
        except Exception as e:  # noqa: BLE001
            logger.error("PDF load failed completely: %s", str(e))
            return None, None

    # ======================================================================
    # Prompt
    # ======================================================================
    def _build_extraction_prompt(self) -> str:
        """Build the extraction prompt (injection defense + instructions)."""
        categories_list = "\n".join(f"  - {c}" for c in self.categories)
        return f"""{get_injection_defense_prompt()}Analyze this receipt image carefully (US or international). Extract ALL information into a JSON object.

CRITICAL INSTRUCTIONS:
1. Read EVERY visible line carefully before extracting. Do NOT invent text you cannot see.
2. The date format MUST be MM/DD/YYYY. If the year is 2-digit (e.g. "24"), convert to 4-digit (2024). Korean/Japanese receipts write the date YEAR-first (use 년/월/일 or 年/月/日 markers to find month vs day).
3. ALL monetary values must be plain numbers (no currency symbol in JSON values).
4. Separate subtotal, tax, and tip clearly.
5. The total is the amount CHARGED. Do NOT report "Cash Tendered", "Amount Received", or "Change" as the total — prefer "Amount Paid", "Total", "Grand Total".
6. If the receipt is from a restaurant and tip is handwritten, estimate carefully and mention uncertainty in notes.
7. For vendor name, use the OFFICIAL business name (e.g. "Walmart Supercenter"). Romanize non-Latin vendor names in Title Case — do not translate.
8. State must be a 2-letter US state code when clearly visible (e.g. "TX"). Leave null for non-US receipts.
9. For payment method, look for "VISA", "MASTERCARD", "AMEX", "DISCOVER", "DEBIT", "CASH", etc.
10. For card_last_4, extract only the last 4 digits if shown (often masked like ****1234). If absent, return null — do NOT guess.

MATHEMATICAL VERIFICATION:
- Verify: subtotal + tax + tip = total (within $0.02 tolerance).
- If tip is not present (non-restaurant), set tip to 0.
- If subtotal is not separately shown, calculate: subtotal = total - tax - tip.

CATEGORY SELECTION (choose the BEST match):
{categories_list}

CONFIDENCE SCORING (compute it; do NOT default to 0.95):
- 0.95 to 1.0: every field clearly readable, amounts reconcile.
- 0.85 to 0.94: one or two secondary fields slightly unclear.
- 0.70 to 0.84: several fields hard to read, some guessing.
- Below 0.70: a required field (vendor/date/total) is unreadable.
When confidence is below 1.0, briefly state in "notes" which field lowered it.

RESPOND WITH ONLY THIS JSON STRUCTURE (no markdown, no explanation, no backticks):
{{
  "date": "MM/DD/YYYY or null if unreadable",
  "vendor": "Official business name",
  "location": "City, ST",
  "state": "XX",
  "subtotal": 0.00,
  "tax": 0.00,
  "tip": 0.00,
  "total": 0.00,
  "payment_method": "VISA/MASTERCARD/AMEX/DISCOVER/DEBIT/CASH/null",
  "card_last_4": "1234 or null",
  "category": "Category name from list above",
  "confidence": 0.95,
  "notes": "Any uncertainties or special observations"
}}"""

    # ======================================================================
    # Data normalization
    # ======================================================================
    def _normalize_data(self, data: dict) -> dict:
        """Normalize types/formats (amounts, date, strings, category, conf)."""
        for key in ("subtotal", "tax", "tip", "total"):
            val = data.get(key)
            if val is None or val == "" or val == "null":
                data[key] = 0.0
            elif isinstance(val, str):
                cleaned = re.sub(r"[^\d.\-]", "", val)
                try:
                    data[key] = round(float(cleaned), 2) if cleaned else 0.0
                except ValueError:
                    data[key] = 0.0
            else:
                data[key] = round(float(val), 2)

        date_val = data.get("date")
        if date_val and isinstance(date_val, str) and date_val.lower() != "null":
            data["date"] = self._normalize_date(date_val)
        else:
            data["date"] = None

        for key in ("vendor", "location", "state", "payment_method",
                    "card_last_4", "category", "notes"):
            val = data.get(key)
            if val and isinstance(val, str):
                val = val.strip()
                data[key] = None if val.lower() in ("null", "none", "n/a", "") else val
            else:
                data[key] = None

        if data.get("state"):
            state = data["state"].upper().strip()
            data["state"] = state if (len(state) == 2 and state.isalpha()) else None

        if data.get("card_last_4"):
            digits = re.sub(r"\D", "", str(data["card_last_4"]))
            data["card_last_4"] = digits[-4:] if len(digits) >= 4 else (digits or None)

        if data.get("category") not in self.categories:
            data["category"] = self._find_closest_category(data.get("category", ""))

        conf = data.get("confidence")
        if conf is None or not isinstance(conf, (int, float)):
            data["confidence"] = 0.5
        else:
            data["confidence"] = max(0.0, min(1.0, float(conf)))

        defaults = {
            "date": None, "vendor": None, "location": None, "state": None,
            "subtotal": 0.0, "tax": 0.0, "tip": 0.0, "total": 0.0,
            "payment_method": None, "card_last_4": None,
            "category": "Miscellaneous", "confidence": 0.5, "notes": None,
        }
        for k, v in defaults.items():
            data.setdefault(k, v)
        return data

    def _normalize_date(self, date_str: str) -> str:
        """Convert common date formats to MM/DD/YYYY."""
        date_str = date_str.strip()
        patterns = [
            r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$",
            r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})$",
            r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$",
        ]
        for pattern in patterns:
            match = re.match(pattern, date_str)
            if match:
                groups = match.groups()
                if len(groups[0]) == 4:
                    y, m, d = int(groups[0]), int(groups[1]), int(groups[2])
                elif len(groups[2]) == 2:
                    m, d, y = int(groups[0]), int(groups[1]), int(groups[2])
                    y = 2000 + y if y < 50 else 1900 + y
                else:
                    m, d, y = int(groups[0]), int(groups[1]), int(groups[2])
                try:
                    return datetime(y, m, d).strftime("%m/%d/%Y")
                except ValueError:
                    pass

        month_names = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5,
                       "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
                       "nov": 11, "dec": 12}
        match = re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", date_str)
        if match:
            month_str = match.group(1)[:3].lower()
            if month_str in month_names:
                try:
                    return datetime(int(match.group(3)), month_names[month_str],
                                    int(match.group(2))).strftime("%m/%d/%Y")
                except ValueError:
                    pass

        logger.warning("Date normalization failed (keeping original): %s", date_str)
        return date_str

    def _find_closest_category(self, input_cat: str) -> str:
        """Map an input string to the closest valid category."""
        if not input_cat:
            return "Miscellaneous"
        input_lower = input_cat.lower()
        keyword_map = {
            "meal": "Meals & Entertainment", "food": "Meals & Entertainment",
            "restaurant": "Meals & Entertainment", "dining": "Meals & Entertainment",
            "coffee": "Meals & Entertainment", "lunch": "Meals & Entertainment",
            "dinner": "Meals & Entertainment", "breakfast": "Meals & Entertainment",
            "transport": "Transportation", "uber": "Transportation",
            "lyft": "Transportation", "taxi": "Transportation", "ride": "Transportation",
            "hotel": "Lodging", "lodg": "Lodging", "motel": "Lodging",
            "airbnb": "Lodging", "inn": "Lodging",
            "office": "Office Supplies", "supply": "Office Supplies",
            "supplie": "Office Supplies", "stationer": "Office Supplies",
            "client": "Client Entertainment", "entertain": "Client Entertainment",
            "travel": "Travel Expenses", "flight": "Travel Expenses",
            "airline": "Travel Expenses", "rental": "Travel Expenses",
            "gas": "Gas & Fuel", "fuel": "Gas & Fuel", "petrol": "Gas & Fuel",
            "shell": "Gas & Fuel", "chevron": "Gas & Fuel",
            "park": "Parking & Tolls", "toll": "Parking & Tolls",
            "phone": "Communication", "internet": "Communication",
            "telecom": "Communication", "wireless": "Communication",
        }
        for keyword, category in keyword_map.items():
            if keyword in input_lower:
                return category
        for cat in self.categories:
            if cat.lower() == input_lower:
                return cat
        return "Miscellaneous"

    # ======================================================================
    # Amount cross-validation
    # ======================================================================
    def _cross_validate_amounts(self, data: dict) -> dict:
        """Verify subtotal + tax + tip ~= total; auto-correct or flag."""
        subtotal = data.get("subtotal", 0.0)
        tax = data.get("tax", 0.0)
        tip = data.get("tip", 0.0)
        total = data.get("total", 0.0)

        if total <= 0:
            if subtotal > 0:
                data["total"] = round(subtotal + tax + tip, 2)
                data["notes"] = self._append_note(
                    data.get("notes"), "Total auto-calculated (subtotal+tax+tip)")
            return data

        calculated = round(subtotal + tax + tip, 2)
        diff = abs(calculated - total)
        if diff <= 0.02:
            return data
        if subtotal == 0 and total > 0:
            data["subtotal"] = round(total - tax - tip, 2)
            data["notes"] = self._append_note(
                data.get("notes"), "Subtotal back-calculated (total-tax-tip)")
        else:
            data["notes"] = self._append_note(
                data.get("notes"),
                f"Amount mismatch: {subtotal}+{tax}+{tip}={calculated} vs total={total}")
            data["confidence"] = min(data.get("confidence", 1.0), 0.88)
        return data

    @staticmethod
    def _append_note(existing, new_note: str) -> str:
        if existing and str(existing).strip():
            return f"{str(existing).strip()} | {new_note}"
        return new_note

    # ======================================================================
    # Validation
    # ======================================================================
    def _validate_data(self, data: dict):
        """Return (is_valid, error_list)."""
        errors = []
        if not data.get("vendor"):
            errors.append("Missing vendor name")
        if not data.get("total") or data["total"] <= 0:
            errors.append("Missing or zero total amount")
        if data.get("date"):
            try:
                parsed = datetime.strptime(data["date"], "%m/%d/%Y")
                if parsed > datetime.now():
                    errors.append("Future date")
                if parsed.year < 2015:
                    errors.append("Date too old")
            except ValueError:
                errors.append(f"Invalid date format: {data['date']}")
        total = data.get("total", 0)
        if total > self.config["validation"]["max_amount"]:
            errors.append(f"High amount (${total:,.2f})")
        for key in ("subtotal", "tax", "tip", "total"):
            if data.get(key, 0) < 0:
                errors.append(f"Negative {key}")
        if data.get("category") not in self.categories:
            errors.append(f"Invalid category: {data.get('category')}")
        return (len(errors) == 0, errors)

    def _identify_issues(self, data: dict, confidence: float) -> str:
        issues = []
        if confidence < 0.7:
            issues.append("Very low confidence")
        elif confidence < self.review_threshold:
            issues.append("Low confidence")
        if not data.get("vendor"):
            issues.append("Unclear vendor")
        if not data.get("date"):
            issues.append("Unclear date")
        if data.get("total", 0) > 500:
            issues.append("High amount")
        notes = data.get("notes") or ""
        if any(w in notes.lower() for w in
               ("unclear", "uncertain", "unreadable", "blurry", "handwritten")):
            issues.append("Hard to read sections")
        return " / ".join(issues) if issues else "Review needed"

    @staticmethod
    def _error_result(error_msg: str) -> dict:
        return {
            "success": False, "data": None, "confidence": 0.0,
            "needs_review": False, "issue": None, "error": error_msg,
        }
