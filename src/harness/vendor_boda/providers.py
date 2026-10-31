# -*- coding: utf-8 -*-
"""
providers.py - Multi-provider OCR backend (Gemini primary, Claude fallback)
===========================================================================
Self-contained provider layer for the receipt OCR engine.

- Gemini 2.5 Flash is the primary provider (fast + cheap structured vision).
- Claude is the fallback when Gemini's circuit is open or it returns nothing.
- Each provider has its own circuit breaker so a Gemini outage never blocks
  the healthy Claude fallback, and vice versa.
- Provider error strings are redacted before logging: both SDKs occasionally
  echo request-body fragments (incl. base64 image data) into exception text,
  and receipt images are PII.

No internal/company dependencies — only `anthropic`, `google-genai`, stdlib.
"""

import base64
import json
import logging
import re
import threading
import time

logger = logging.getLogger("OcrProviders")

# Provider SDK error strings sometimes embed base64 payload fragments.
# Strip any base64-looking run >= 32 chars before logging so image data
# cannot leak into operational logs.
_BASE64_RUN_RE = re.compile(r"[A-Za-z0-9+/=]{32,}")


def redact_provider_error(err: object, max_len: int = 200) -> str:
    """Return a log-safe, truncated excerpt of a provider exception."""
    text = str(err) if err is not None else ""
    text = _BASE64_RUN_RE.sub("[REDACTED_BASE64]", text)
    return text[:max_len]


# ---------------------------------------------------------------------------
# Circuit breaker (per provider)
# ---------------------------------------------------------------------------
class CircuitBreaker:
    """Minimal thread-safe circuit breaker.

    After `open_after` consecutive failures the circuit opens for
    `cooldown_seconds`; while open, callers should skip the provider. Once
    the cooldown expires a single half-open probe is allowed through — its
    result (success/failure) closes or re-opens the circuit.
    """

    def __init__(self, open_after: int = 3, cooldown_seconds: int = 60):
        self._open_after = max(1, int(open_after))
        self._cooldown = max(1, int(cooldown_seconds))
        self._lock = threading.Lock()
        self._consecutive = 0
        self._opened_at = None  # monotonic timestamp, or None when closed

    def is_open(self) -> bool:
        """True if requests should be short-circuited right now."""
        with self._lock:
            if self._opened_at is None:
                return False
            if time.monotonic() - self._opened_at < self._cooldown:
                return True
            # Cooldown expired — allow one probe through (half-open).
            return False

    def record_success(self) -> None:
        with self._lock:
            was_open = self._opened_at is not None
            self._consecutive = 0
            self._opened_at = None
            if was_open:
                logger.info("[CIRCUIT] circuit closed (probe succeeded)")

    def record_failure(self) -> None:
        with self._lock:
            self._consecutive += 1
            if self._consecutive >= self._open_after:
                self._opened_at = time.monotonic()
                logger.error(
                    "[CIRCUIT] OPEN after %d consecutive failures; "
                    "short-circuiting for %ds",
                    self._consecutive, self._cooldown,
                )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------
def parse_response(response_text: str):
    """Extract the first valid JSON object/array from an OCR response.

    Handles markdown code fences and surrounding prose. Tries JSON starts in
    textual order (earliest-first) so a top-level object containing a nested
    array is not mis-parsed as the inner array alone.
    """
    if not response_text:
        return None
    try:
        cleaned = response_text.strip()
        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
            if match:
                cleaned = match.group(1)

        decoder = json.JSONDecoder()
        starts = sorted(
            idx for idx in (cleaned.find("{"), cleaned.find("[")) if idx != -1
        )
        for index in starts:
            try:
                data, _ = decoder.raw_decode(cleaned[index:])
                return data
            except json.JSONDecodeError:
                continue

        logger.error("No parseable JSON found in response")
        return None
    except Exception as e:  # noqa: BLE001 - parser must never raise to caller
        logger.error("Parse error: %s", str(e))
        return None


# ---------------------------------------------------------------------------
# Claude provider
# ---------------------------------------------------------------------------
def call_claude_with_retry(client, cfg: dict, page_payloads, prompt: str,
                           max_retries: int, retry_delay: int):
    """Call the Anthropic API with exponential-backoff retry.

    page_payloads: list of (base64_str, media_type) tuples.
    Returns the response text, or None on failure.
    """
    import anthropic

    model = cfg.get("model", "")
    max_tokens = int(cfg.get("max_tokens", 1500) or 1500)
    temperature = float(cfg.get("temperature", 0.0) or 0.0)

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("OCR call (provider=claude, model=%s, attempt %d/%d)",
                        model, attempt, max_retries)

            content_blocks = []
            for data_b64, media_type in page_payloads:
                if media_type == "application/pdf":
                    content_blocks.append({
                        "type": "document",
                        "source": {"type": "base64",
                                   "media_type": "application/pdf",
                                   "data": data_b64},
                    })
                else:
                    content_blocks.append({
                        "type": "image",
                        "source": {"type": "base64",
                                   "media_type": media_type,
                                   "data": data_b64},
                    })
            content_blocks.append({"type": "text", "text": prompt})

            # Disable extended thinking — this OCR task needs no reasoning
            # tokens. Older SDKs without the param fall back gracefully.
            create_kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": content_blocks}],
            }
            try:
                message = client.messages.create(
                    thinking={"type": "disabled"}, **create_kwargs)
            except TypeError:
                message = client.messages.create(**create_kwargs)

            if message.content and len(message.content) > 0:
                text = message.content[0].text
                logger.info("Claude response received (%d chars)", len(text))
                return text
            logger.warning("Empty response from Claude")
            return None

        except anthropic.RateLimitError:
            wait = retry_delay * (2 ** (attempt - 1))
            logger.warning("Claude rate limited - waiting %ds", wait)
            time.sleep(wait)
        except anthropic.APIConnectionError as e:
            wait = retry_delay * attempt
            logger.warning("Claude connection error: %s - retry in %ds",
                           redact_provider_error(e), wait)
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            logger.error("Claude API error (%s): %s",
                         e.status_code, redact_provider_error(e))
            if e.status_code >= 500:
                time.sleep(retry_delay * attempt)
                continue
            return None  # 4xx: don't retry
        except Exception as e:  # noqa: BLE001
            logger.error("Claude unexpected error: %s", redact_provider_error(e))
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            return None

    logger.error("Claude max retries exhausted")
    return None


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------
def build_gemini_client(api_key: str, timeout_sec: float = 60.0):
    """Create a Gemini client with an explicit HTTP timeout.

    The SDK default is "no timeout"; a hung request would otherwise block an
    OCR worker forever. Older SDKs without http_options fall back gracefully.
    """
    from google import genai
    try:
        return genai.Client(
            api_key=api_key,
            http_options={"timeout": int(timeout_sec * 1000)},  # SDK uses ms
        )
    except TypeError:
        return genai.Client(api_key=api_key)


def _classify_gemini_error(err: str) -> str:
    """Bucket a Gemini error string: auth | next_model | retry_same."""
    if "403" in err or "PERMISSION_DENIED" in err or "UNAUTHENTICATED" in err:
        return "auth"
    if "503" in err or "UNAVAILABLE" in err:
        return "next_model"
    return "retry_same"


def call_gemini_with_retry(client, cfg: dict, page_payloads, prompt: str,
                           max_retries: int, retry_delay: int):
    """Call the Gemini API with retry/backoff. Returns text or None."""
    from google.genai import types

    model = cfg.get("model", "gemini-2.5-flash")
    max_tokens = int(cfg.get("max_tokens", 1500) or 1500)
    temperature = float(cfg.get("temperature", 0.0) or 0.0)

    contents = []
    for data_b64, media_type in page_payloads:
        if media_type in ("application/pdf", "image/jpeg", "image/png",
                          "image/webp"):
            contents.append(types.Part.from_bytes(
                data=base64.b64decode(data_b64), mime_type=media_type))
        else:
            logger.warning("Unsupported Gemini mime type %s; skipping",
                           media_type)
    contents.append(prompt)

    effective_max_tokens = max_tokens
    truncated_once = False
    attempt = 1
    budget = max_retries
    while attempt <= budget:
        try:
            logger.info("OCR call (provider=gemini, model=%s, attempt %d/%d)",
                        model, attempt, budget)
            gen_config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=effective_max_tokens,
                response_mime_type="application/json",
            )
            response = client.models.generate_content(
                model=model, contents=contents, config=gen_config)

            finish_reason = None
            try:
                candidates = getattr(response, "candidates", None) or []
                if len(candidates) > 0:
                    fr = getattr(candidates[0], "finish_reason", None)
                    finish_reason = str(fr) if fr else None
            except (AttributeError, IndexError, TypeError):
                pass

            text = getattr(response, "text", None)

            # If truncated at the token cap, double it once and retry — most
            # multi-page receipts fit within 3000 tokens.
            if (finish_reason and "MAX_TOKENS" in finish_reason
                    and not truncated_once):
                effective_max_tokens *= 2
                truncated_once = True
                budget += 1
                logger.warning("Gemini truncated; retrying with doubled budget "
                               "(%d tokens)", effective_max_tokens)
                attempt += 1
                continue

            if text:
                logger.info("Gemini response received (%d chars)", len(text))
                return text
            logger.warning("Empty response from Gemini (finish=%s)",
                           finish_reason)
            return None

        except Exception as exc:  # noqa: BLE001
            err = str(exc)
            err_safe = redact_provider_error(exc)
            action = _classify_gemini_error(err)
            if action == "auth":
                logger.error("Gemini auth error: %s", err_safe)
                return None
            wait = (retry_delay * (2 ** (attempt - 1))
                    if ("429" in err or "RESOURCE_EXHAUSTED" in err)
                    else retry_delay * attempt)
            logger.warning("Gemini error (attempt %d/%d): %s - retry in %ds",
                           attempt, budget, err_safe, wait)
            if attempt < budget:
                time.sleep(wait)
                attempt += 1
                continue
            return None

    logger.error("Gemini max retries exhausted")
    return None
