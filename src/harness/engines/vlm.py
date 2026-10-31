"""vlm.py - Vision-LLM readers: tier 2 (local, Ollama) and tier 3 (cloud chain).

Every reader returns the same record shape:

    {
      "engine": "qwen3-vl:2b" | "gemini-3.8-flash" | "gemini-3.1-flash-lite" | "claude-haiku-5-5",
      "provider": "ollama" | "gemini" | "claude" | "none",
      "raw_text": str,                 # exactly what the model returned
      "data": dict | None,             # parsed + sanitized JSON (None if unparseable)
      "sanitizer": {"is_safe": bool, "warnings": [...]},
      "usage": {"input_tokens": int, "output_tokens": int},
      "cost_usd": float | None,        # 0.0 for local, None if price unknown
      "latency_ms": int,
      "attempts": [ {provider, model, ok, error} ... ],   # chain trace
      "chain": ["model", ...],         # the models this call was allowed to use
    }

Reused from the vendored boda code: parse_response (fence-tolerant JSON),
CircuitBreaker, redact_provider_error, and the sanitizer. The prompt and
schema come from harness.schema so all tiers read with identical instructions.
"""

from __future__ import annotations

import base64
import io
import mimetypes
import time
from pathlib import Path

import requests

from ..keys import require_key
from ..schema import RECEIPT_JSON_SCHEMA, extraction_prompt
from ..vendor_boda.providers import CircuitBreaker, parse_response, redact_provider_error
from ..vendor_boda.sanitizer import validate_ai_response

# USD per 1M tokens (input, output), paid tier, verified on the official price
# page 2026-10-31 (see results/pricing_sources.md).
PRICES_PER_1M = {
    "gemini-3.8-flash": (0.75, 3.75),        # through 2026-12-31; doubles 2027-01-01
    "gemini-3.6-flash": (0.75, 3.75),        # through 2026-12-31; doubles 2027-01-01
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "claude-haiku-5-5": (0.10, 0.50),        # Anthropic model table, cached 2026-10-06
}

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5vl:3b"                # no thinking mode; qwen3-vl:2b thinks past the token cap
GEMINI_MODEL = "gemini-3.6-flash"            # 3.8-flash returned 503/504 all evening on 2026-10-31
GEMINI_LITE_MODEL = "gemini-3.1-flash-lite"
CLAUDE_MODEL = "claude-haiku-5-5"

# Production-style cheap-first chain (ADR-0010/0012 pattern): cheap Gemini,
# then the stronger Gemini, then a different vendor.
DEFAULT_CHAIN = (("gemini", GEMINI_LITE_MODEL), ("gemini", GEMINI_MODEL), ("claude", CLAUDE_MODEL))

# Max long side sent to each tier. SROIE scans are ~5000x7000 px; vision
# models tile or resize internally, so sending that is pure upload cost.
MAX_SIDE_CLOUD = 1600
MAX_SIDE_LOCAL = 1024
CLOUD_TIMEOUT_S = 120

_circuits: dict[str, CircuitBreaker] = {}
_gemini_client = None
_claude_client = None


def _circuit(key: str) -> CircuitBreaker:
    if key not in _circuits:
        _circuits[key] = CircuitBreaker(open_after=3, cooldown_seconds=60)
    return _circuits[key]


def _image_payload(image_path: Path, max_side: int) -> tuple[str, str]:
    """Return (base64, mime) of the image downscaled to max_side (JPEG)."""
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"
    mime = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
    return base64.b64encode(image_path.read_bytes()).decode("ascii"), mime


def _cost(model: str, inp: int, out: int) -> float | None:
    pi, po = PRICES_PER_1M.get(model, (None, None))
    if pi is None or po is None:
        return None
    return round((inp * pi + out * po) / 1_000_000, 6)


def _finish(engine: str, provider: str, raw_text: str | None, usage: dict,
            t0: float, attempts: list[dict], chain: list[str]) -> dict:
    data = parse_response(raw_text) if raw_text else None
    if isinstance(data, list):
        data = data[0] if data and isinstance(data[0], dict) else None
    sanitizer = {"is_safe": None, "warnings": []}
    if isinstance(data, dict):
        is_safe, data, warnings = validate_ai_response(dict(data))
        sanitizer = {"is_safe": bool(is_safe), "warnings": list(warnings)}
    else:
        data = None
    return {
        "engine": engine,
        "provider": provider,
        "raw_text": raw_text or "",
        "data": data,
        "sanitizer": sanitizer,
        "usage": usage,
        "cost_usd": 0.0 if provider == "ollama" else _cost(engine, usage.get("input_tokens", 0),
                                                           usage.get("output_tokens", 0)),
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "attempts": attempts,
        "chain": chain,
    }


# ---------------------------------------------------------------------------
# Tier 2: local VLM through Ollama
# ---------------------------------------------------------------------------
def run_ollama(image_path: str | Path, model: str = OLLAMA_MODEL,
               prompt: str | None = None, timeout: int = 900) -> dict:
    image_path = Path(image_path)
    b64, _mime = _image_payload(image_path, MAX_SIDE_LOCAL)
    prompt = prompt or extraction_prompt()
    t0 = time.perf_counter()
    attempts: list[dict] = []

    def call(fmt):
        body = {
            "model": model,
            "stream": False,
            "think": False,           # Qwen3 thinking mode otherwise eats num_predict and returns empty content
            "format": fmt,
            "options": {"temperature": 0, "num_predict": 1024},
            "messages": [{"role": "user", "content": prompt, "images": [b64]}],
        }
        r = requests.post(OLLAMA_URL, json=body, timeout=timeout)
        if r.status_code >= 400:
            raise requests.HTTPError(f"{r.status_code}: {r.text[:200]}", response=r)
        return r.json()

    try:
        resp = call(RECEIPT_JSON_SCHEMA)
        attempts.append({"provider": "ollama", "model": model, "ok": True, "error": None, "format": "schema"})
    except requests.HTTPError as exc:
        attempts.append({"provider": "ollama", "model": model, "ok": False,
                         "error": redact_provider_error(exc), "format": "schema"})
        resp = call("json")   # grammar may reject the schema; plain JSON mode as fallback
        attempts.append({"provider": "ollama", "model": model, "ok": True, "error": None, "format": "json"})

    text = (resp.get("message") or {}).get("content", "")
    usage = {"input_tokens": int(resp.get("prompt_eval_count", 0) or 0),
             "output_tokens": int(resp.get("eval_count", 0) or 0),
             "model_total_duration_ms": int((resp.get("total_duration", 0) or 0) / 1e6)}
    return _finish(model, "ollama", text, usage, t0, attempts, [model])


# ---------------------------------------------------------------------------
# Tier 3: cloud providers
# ---------------------------------------------------------------------------
def _gemini_configs(types):
    """Thinking is forced to the minimum (ADR-0011 pattern): receipts need
    reading, not reasoning, and thinking tokens are billed as output. Try the
    Gemini 3 'thinking_level' knob, then the 2.x 'thinking_budget', then none."""
    base = dict(temperature=0.0, max_output_tokens=2048, response_mime_type="application/json")
    variants = []
    # Order learned on 2026-10-31: budget=0 works on 3.5/3.6 Flash, the Lite
    # models accept only "none", and 3.8 Flash rejects level "minimal".
    for thinking in (
        lambda: types.ThinkingConfig(thinking_budget=0),
        lambda: None,
        lambda: types.ThinkingConfig(thinking_level="low"),
    ):
        try:
            tc = thinking()
        except (TypeError, ValueError):
            continue
        kwargs = dict(base)
        if tc is not None:
            kwargs["thinking_config"] = tc
        try:
            variants.append(types.GenerateContentConfig(response_json_schema=RECEIPT_JSON_SCHEMA, **kwargs))
        except (TypeError, ValueError):
            variants.append(types.GenerateContentConfig(**kwargs))
    return variants


def _call_gemini(image_path: Path, prompt: str, model: str, max_attempts: int) -> tuple[str | None, dict, list[dict]]:
    global _gemini_client
    from google import genai
    from google.genai import types

    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=require_key("GEMINI_API_KEY"),
                                      http_options={"timeout": CLOUD_TIMEOUT_S * 1000})
    b64, mime = _image_payload(image_path, MAX_SIDE_CLOUD)
    part = types.Part.from_bytes(data=base64.b64decode(b64), mime_type=mime)
    configs = _gemini_configs(types)
    cfg_idx = 0
    attempts: list[dict] = []
    attempt = 1
    while attempt <= max_attempts:
        cfg = configs[min(cfg_idx, len(configs) - 1)]
        try:
            resp = _gemini_client.models.generate_content(model=model, contents=[part, prompt], config=cfg)
            um = getattr(resp, "usage_metadata", None)
            usage = {"input_tokens": int(getattr(um, "prompt_token_count", 0) or 0),
                     "output_tokens": int(getattr(um, "candidates_token_count", 0) or 0),
                     "thinking_tokens": int(getattr(um, "thoughts_token_count", 0) or 0)}
            text = getattr(resp, "text", None)
            attempts.append({"provider": "gemini", "model": model, "ok": bool(text), "error": None,
                             "attempt": attempt, "config": cfg_idx})
            if text:
                return text, usage, attempts
        except Exception as exc:  # noqa: BLE001 - every provider error is recorded, not raised
            err = redact_provider_error(exc)
            attempts.append({"provider": "gemini", "model": model, "ok": False, "error": err,
                             "attempt": attempt, "config": cfg_idx})
            if "400" in err and cfg_idx < len(configs) - 1:
                cfg_idx += 1          # this model rejects that config (usually the thinking knob): next variant, same attempt budget
                continue
            if "403" in err or "404" in err or "PERMISSION_DENIED" in err or "UNAUTHENTICATED" in err:
                break
            if attempt < max_attempts:
                time.sleep(3 * attempt)
        attempt += 1
    return None, {"input_tokens": 0, "output_tokens": 0}, attempts


def _call_claude(image_path: Path, prompt: str, model: str, max_attempts: int) -> tuple[str | None, dict, list[dict]]:
    global _claude_client
    import anthropic

    if _claude_client is None:
        _claude_client = anthropic.Anthropic(api_key=require_key("ANTHROPIC_API_KEY"),
                                             max_retries=0, timeout=float(CLOUD_TIMEOUT_S))
    b64, mime = _image_payload(image_path, MAX_SIDE_CLOUD)
    attempts: list[dict] = []
    for attempt in range(1, max_attempts + 1):
        try:
            resp = _claude_client.messages.create(
                model=model,
                max_tokens=2048,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                    {"type": "text", "text": prompt},
                ]}],
            )
            usage = {"input_tokens": int(resp.usage.input_tokens), "output_tokens": int(resp.usage.output_tokens)}
            if resp.stop_reason == "refusal":
                attempts.append({"provider": "claude", "model": model, "ok": False, "error": "refusal", "attempt": attempt})
                return None, usage, attempts
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            attempts.append({"provider": "claude", "model": model, "ok": bool(text), "error": None, "attempt": attempt})
            if text:
                return text, usage, attempts
        except anthropic.RateLimitError as exc:
            attempts.append({"provider": "claude", "model": model, "ok": False, "error": redact_provider_error(exc), "attempt": attempt})
            if attempt < max_attempts:
                time.sleep(5 * attempt)
        except anthropic.APIStatusError as exc:
            attempts.append({"provider": "claude", "model": model, "ok": False, "error": redact_provider_error(exc), "attempt": attempt})
            if exc.status_code < 500:
                break
            if attempt < max_attempts:
                time.sleep(3 * attempt)
        except anthropic.APIConnectionError as exc:
            attempts.append({"provider": "claude", "model": model, "ok": False, "error": redact_provider_error(exc), "attempt": attempt})
            if attempt < max_attempts:
                time.sleep(3 * attempt)
    return None, {"input_tokens": 0, "output_tokens": 0}, attempts


def run_cloud_chain(image_path: str | Path, chain=DEFAULT_CHAIN, prompt: str | None = None,
                    fast_fail: bool = True) -> dict:
    """Walk a (provider, model) chain. With fast_fail (ADR-0012 pattern) every
    non-last link gets 1 attempt and only the last link gets 3; a single-link
    chain therefore gets 3 attempts, which is the right setting for measuring
    one model on its own. Circuit breakers skip a link that failed 3 times in
    a row until its cooldown passes. A missing key skips the link, never fatal."""
    image_path = Path(image_path)
    prompt = prompt or extraction_prompt()
    chain = list(chain)
    t0 = time.perf_counter()
    all_attempts: list[dict] = []
    models = [m for _, m in chain]
    for i, (provider, model) in enumerate(chain):
        is_last = i == len(chain) - 1
        budget = 3 if (is_last or not fast_fail) else 1
        circuit = _circuit(f"{provider}:{model}")
        if circuit.is_open():
            all_attempts.append({"provider": provider, "model": model, "ok": False, "error": "circuit_open"})
            continue
        try:
            if provider == "gemini":
                text, usage, attempts = _call_gemini(image_path, prompt, model, budget)
            elif provider == "claude":
                text, usage, attempts = _call_claude(image_path, prompt, model, budget)
            else:
                raise ValueError(f"unknown provider {provider}")
        except RuntimeError as exc:   # missing key for this provider
            all_attempts.append({"provider": provider, "model": model, "ok": False, "error": str(exc)[:120]})
            continue
        all_attempts.extend(attempts)
        if text:
            circuit.record_success()
            return _finish(model, provider, text, usage, t0, all_attempts, models)
        circuit.record_failure()
    return _finish("none", "none", None, {"input_tokens": 0, "output_tokens": 0}, t0, all_attempts, models)
