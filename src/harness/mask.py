"""mask.py - hide personal data on a receipt image before it goes to the cloud (plan: docs/plan-pii-mask.md).

This module is the one place for the masking experiment's paths and checks:
    pii_paths(results_root, manifest)   public (committed) and local-only (git-ignored) locations
    check_tags(record, n_tags)          the tag check run on a cloud answer read from a masked image

Masking rules (label, pattern, protection, gate) are added in step 2 of the plan and frozen before labels.
verify.py is deliberately not changed: its sha256 is part of the recorded gate experiment
(results*/gate_total_label/comparison.json), so the tag check lives here and 04_harness.py calls it
when run with --gates tags.
"""
from __future__ import annotations

import re
from pathlib import Path

from .verify import Flag

ROOT = Path(__file__).resolve().parents[2]
LOCAL_ROOT = ROOT / "data" / "raw" / "pii_local"      # under data/raw/, which .gitignore already excludes

TAG = re.compile(r"\[P(\d+)\]")
BROKEN_TAG = re.compile(r"\[\s*P\s*\d+(?!\d|\s*\])|(?<![\[\d])P\d+\s*\]")


def pii_paths(results_root: str | Path, manifest: str | Path) -> dict:
    """Every path of the masking experiment for one dataset. Dataset name = manifest stem."""
    dataset = Path(manifest).stem
    pub = Path(results_root) / "pii"
    loc = LOCAL_ROOT / dataset
    return {
        "dataset": dataset,
        "public": pub,
        "sample": pub / "sample.json",
        "freeze": pub / "freeze.json",
        "local": loc,
        "boxes": loc / "boxes",
        "jobs": loc / "jobs.jsonl",
        "labels": loc / "labels",
        "mask_maps": loc / "mask_maps",
        "images": loc / "images",
        "manifests": loc / "manifests",
        "post_ocr": loc / "post_ocr",
        "budget": LOCAL_ROOT / "budget.json",
    }


def check_tags(record: dict | None, n_tags: int | None) -> list[Flag]:
    """Flags for tags in a cloud answer. Tags issued for a receipt are [P1]..[Pn].

    G_TAG unissued  a string field holds a tag above n (or a broken tag such as "[P3" or "P3]")
    G_TAG date      the date field holds any tag (total is numeric; a tag there fails the sanitizer)
    """
    data = (record or {}).get("data")
    if not isinstance(data, dict):
        return []
    n = n_tags or 0
    flags: list[Flag] = []
    for field, value in data.items():
        if not isinstance(value, str):
            continue
        found = [int(m) for m in TAG.findall(value)]
        if any(t < 1 or t > n for t in found) or BROKEN_TAG.search(TAG.sub("", value)):
            flags.append(Flag("G_TAG", f"unissued:{field}"))
        if field == "date" and (found or BROKEN_TAG.search(value)):
            flags.append(Flag("G_TAG", "date"))
    return flags
