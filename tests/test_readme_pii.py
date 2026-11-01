"""The README masking block carries the disclosures the plan requires (docs/plan-pii-mask.md, Publishing)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pii_block_disclosures():
    spec = importlib.util.spec_from_file_location("r22", ROOT / "scripts" / "22_readme.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = mod.block_pii()
    for must in ("model-labeled (Gemini 3.1 Flash-Lite)", "30 receipts per dataset", "frozen and committed before any label",
                 "disclosed revision", "known misses", "saw sample text", "not decidable", "spending limit was raised"):
        assert must in text, must
