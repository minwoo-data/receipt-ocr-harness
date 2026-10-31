"""keys.py - API key resolution without ever writing a key into this repo.

Resolution order (first hit wins):
  1. Environment variables GEMINI_API_KEY / ANTHROPIC_API_KEY
  2. The user-global file ~/.config/boda/config.json
     (keys: gemini_api_key, anthropic_api_key), which lives outside any
     git repository and is shared with the boda project.

There is deliberately NO project-level config.json path: a file that cannot
exist cannot be committed by accident. Nothing in this module prints or logs
a key value; callers receive the string and pass it straight to the SDK.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_GLOBAL_FILE = Path.home() / ".config" / "boda" / "config.json"
_FILE_KEYS = {
    "GEMINI_API_KEY": "gemini_api_key",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
}


def _from_global_file(env_name: str) -> str | None:
    file_key = _FILE_KEYS.get(env_name)
    if not file_key or not _GLOBAL_FILE.exists():
        return None
    try:
        data = json.loads(_GLOBAL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get(file_key)
    if not value or str(value).startswith("YOUR_"):
        return None
    return str(value)


def get_key(env_name: str) -> str | None:
    """Return the key for ``env_name`` or None. Never raises, never logs."""
    value = os.environ.get(env_name)
    if value and not value.startswith("YOUR_"):
        return value
    return _from_global_file(env_name)


def require_key(env_name: str) -> str:
    value = get_key(env_name)
    if not value:
        raise RuntimeError(
            f"{env_name} not found. Set the environment variable or add it to "
            f"{_GLOBAL_FILE} (outside the repo)."
        )
    return value


def describe() -> dict[str, bool]:
    """Which keys are available (booleans only; safe to print)."""
    return {name: get_key(name) is not None for name in _FILE_KEYS}


if __name__ == "__main__":
    # Prints only True/False per key, never the values.
    for name, present in describe().items():
        print(f"{name}: {'present' if present else 'missing'}")
