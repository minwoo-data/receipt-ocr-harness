"""Masking experiment seams (docs/plan-pii-mask.md, step 1c): paths, tag check, line grouping, bootstrap."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from harness.bootstrap import paired_ci, resample_index  # noqa: E402
from harness.engines.traditional import group_lines  # noqa: E402
from harness.mask import LOCAL_ROOT, check_tags, pii_paths  # noqa: E402


def names(flags):
    return sorted(f.detail for f in flags)


def test_pii_paths_split_public_and_local():
    P = pii_paths(ROOT / "results_wild", "data/manifest/wild200.jsonl")
    assert P["dataset"] == "wild200"
    assert P["sample"] == ROOT / "results_wild" / "pii" / "sample.json"
    for k in ("boxes", "jobs", "labels", "mask_maps", "images", "manifests", "post_ocr"):
        assert LOCAL_ROOT in P[k].parents and "pii_local" in str(P[k]), k
    assert str(LOCAL_ROOT.relative_to(ROOT)).replace("\\", "/").startswith("data/raw/")   # git-ignored root


def test_tags_issued_pass_unissued_and_broken_flag():
    rec = {"data": {"vendor": "SHOP", "date": "2018-06-17", "notes": "cashier [P1], member [P2]", "total": 26.5}}
    assert check_tags(rec, 2) == []
    assert names(check_tags(rec, 1)) == ["unissued:notes"]
    assert names(check_tags({"data": {"notes": "name [P3"}}, 5)) == ["unissued:notes"]
    assert names(check_tags({"data": {"notes": "name P3]"}}, 5)) == ["unissued:notes"]
    assert check_tags({"data": {"notes": "item P100 x2"}}, 0) == []          # a product code is not a tag


def test_tag_in_date_flags_even_when_issued():
    assert "date" in names(check_tags({"data": {"date": "[P1]"}}, 1))
    assert check_tags({"data": None}, 3) == [] and check_tags(None, 0) == []


def test_unmasked_control_has_no_tags():
    assert names(check_tags({"data": {"vendor": "[P1] MART"}}, 0)) == ["unissued:vendor"]


def test_group_lines_assigns_each_detection_its_line():
    # (centre_y, min_x, text) in detection order; a right-aligned amount shares its label's row
    rows = [(100.0, 400.0, "26.50"), (10.0, 0.0, "SHOP"), (101.0, 0.0, "TOTAL"), (55.0, 0.0, "Cashier:ALEX")]  # invented name
    lines, line_of = group_lines(rows, [20.0] * 4)
    assert lines == ["SHOP", "Cashier:ALEX", "TOTAL 26.50"]
    assert line_of == [2, 0, 2, 1]


def test_paired_ci_shape_and_sign():
    a, b = np.array([1, 1, 1, 0] * 10), np.array([1, 0, 1, 0] * 10)
    r = paired_ci(a, b)
    assert r["n"] == 40 and r["point"] == 25.0 and r["ci95"][0] <= 25.0 <= r["ci95"][1]
    assert resample_index(5).shape == (10_000, 5)
