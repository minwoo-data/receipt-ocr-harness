"""Masking rules (docs/plan-pii-mask.md, Masker): one test per row of the Examples table, plus geometry,
the post-mask check, locate_gt, labels and provenance. Detections are built by hand from the dev-set shapes
with invented values (no real name or card number); boxes are invented."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from harness import mask  # noqa: E402

SIDE = mask.load_sidecar(ROOT / "data" / "manifest" / "sroie300.mask.json")

# Receipts the Examples table cites (dataset, key); each must be in that dataset's dev set, never the sample.
CITED = [("results", "X51006414532"), ("results_wild", "W0030_d3759910dd53"), ("results_wild", "W0018_4377"),
         ("results", "X51005719905"), ("results", "X00016469612"), ("results", "X51006311714"),
         ("results_wild", "W0045_90028d102689"), ("results_wild", "W0167_3810"), ("results", "X51006557507"),
         ("results", "X51005230616"), ("results", "X51006008092"), ("results", "X51006401977"),
         ("results", "X51006389963")]


def rec(*lines, date_first=True, fill_to=12):
    """A run_rapidocr-shaped record. Each argument is one printed line: a list of detection texts.
    date_first puts 'Date: 25/03/2018' on line 0, so later lines are below the shop block."""
    rows = ([["Date:", "25/03/2018"]] if date_first else []) + [list(l) for l in lines]
    while sum(len(r) for r in rows) < fill_to:
        rows.append(["ITEM"])
    tokens, out_lines = [], []
    for ln, texts in enumerate(rows):
        x = 10
        for t in texts:
            w = 20 * max(3, len(t))
            tokens.append({"text": t, "conf": 0.99, "id": len(tokens), "line": ln,
                           "box": [[x, 100 * ln + 10], [x + w, 100 * ln + 10], [x + w, 100 * ln + 50], [x, 100 * ln + 50]]})
            x += w + 30
        out_lines.append(" ".join(texts))
    return {"engine": "rapidocr", "lines": out_lines, "tokens": tokens}


def texts_hidden(r, variant="M1"):
    p = mask.plan_mask(r, SIDE, True, variant)
    by_id = {d["id"]: d["text"] for d in r["tokens"]}
    return [by_id[i] for i in p.hide], p


# ---- Examples table, row by row --------------------------------------------------------------------------
def test_label_and_value_in_one_detection():
    assert texts_hidden(rec(["Cashier:ALEX"]))[0] == ["Cashier:ALEX"]
    assert texts_hidden(rec(["STAFF:Sam"]))[0] == ["STAFF:Sam"]


def test_label_after_a_space():
    assert texts_hidden(rec(["YOUR CASHIER TODAY WAS JORDAN"]))[0] == ["YOUR CASHIER TODAY WAS JORDAN"]


def test_value_stops_at_next_label_and_date_is_protected():
    hidden, p = texts_hidden(rec(["Staff:", "LEE", "Date:", "25/03/2018"]))
    assert hidden == ["LEE"] and p.refuse is None


def test_label_with_nothing_after_it_keeps_the_next_line():
    hidden, p = texts_hidden(rec(["Member:"], ["CASH BILL"]))
    assert hidden == [] and p.refuse is None


def test_card_patterns():
    assert texts_hidden(rec(["CARD N0.400000******0000"]))[0] == ["CARD N0.400000******0000"]
    assert texts_hidden(rec(["XXXXXXXXXXXX0000"]))[0] == ["XXXXXXXXXXXX0000"]


def test_label_and_date_in_one_detection_refuses():
    assert texts_hidden(rec(["REG CASHIER 09-16-2015"]))[1].refuse == "label_value_protected"


def test_protected_value_candidate_refuses():
    assert texts_hidden(rec(["Staff:", "25/03/2018"]))[1].refuse == "label_value_protected"


def test_exclude_words():
    assert texts_hidden(rec(["CUSTOMER'SCOPY"]))[0] == []
    hidden, _ = texts_hidden(rec(["ustomer ServiceHot1ine:03-2726-5600"]))     # below the shop block, still kept
    assert hidden == []


def test_label_word_at_the_end_with_nothing_after():
    assert texts_hidden(rec(["BE A POPULAR CARD MEMBER"]))[0] == []


def test_not_an_email():
    assert texts_hidden(rec(["FISHBALLNOODLE@7.0O"]))[0] == []
    assert texts_hidden(rec(["alex@example.com"]))[0] == ["alex@example.com"]


def test_total_is_protected():
    r = rec(["TOTAL 26.50"])
    hidden, p = texts_hidden(r)
    assert hidden == [] and any(r["tokens"][i]["text"] == "TOTAL 26.50" for i in p.protected)


def test_dashed_date_is_not_a_phone():
    assert mask._pattern_hits("25-03-2018", True) == []
    hidden, p = texts_hidden(rec(["Date: 25-03-2018"]))
    assert hidden == [] and p.refuse is None


def test_phone_below_the_shop_block_and_barcode_overmasking():
    assert texts_hidden(rec(["Tel: 012-345 6789"]))[0] == ["Tel: 012-345 6789"]
    assert texts_hidden(rec(["1234567890123"]))[0] == ["1234567890123"]
    # the same phone in the shop block (above the first date or amount line) is the shop's: kept
    assert texts_hidden(rec(["Tel: 012-345 6789"], ["Date: 25/03/2018"], date_first=False))[0] == []


def test_longest_label_wins():
    hidden, p = texts_hidden(rec(["MEMBER NO", "123456"]))
    assert hidden == ["123456"] and p.compare[p.hide[0]] == "123456"


def test_customer_address_after_label():
    assert texts_hidden(rec(["ADDRESS :1 Example Road"]))[0] == ["ADDRESS :1 Example Road"]


# ---- variants, gate, tags --------------------------------------------------------------------------------
def test_U_hides_nothing_and_skips_the_gate():
    p = mask.plan_mask(rec(["Cashier:ALEX"], fill_to=3), SIDE, True, "U")
    assert p.hide == [] and p.refuse is None


def test_few_detections_refuse_M1():
    assert mask.plan_mask(rec(["Cashier:ALEX"], fill_to=3), SIDE, True, "M1").refuse == "few_detections"


def test_M2_hides_shop_block_and_item_names():
    r = rec(["EXAMPLE MART SDN BHD"], ["Date: 25/03/2018"], ["APPLE", "1.00"], ["TOTAL 1.00"], date_first=False)
    hidden_m1, _ = texts_hidden(r, "M1")
    hidden_m2, _ = texts_hidden(r, "M2")
    assert hidden_m1 == [] and "EXAMPLE MART SDN BHD" in hidden_m2 and "APPLE" in hidden_m2
    assert "1.00" not in hidden_m2 and "TOTAL 1.00" not in hidden_m2


def test_tags_in_reading_order():
    _, p = texts_hidden(rec(["Cashier:ALEX"], ["Member No: 123456"]))
    assert [p.tags[i] for i in p.hide] == ["[P1]", "[P2]"]


def test_pattern_on_protected_detection_refuses_card_ignores_phone():
    assert texts_hidden(rec(["TOTAL 26.50 XXXXXXXXXXXX0000"]))[1].refuse == "pattern_on_protected"
    hidden, p = texts_hidden(rec(["TOTAL 26.50 0123 456 789"]))
    assert hidden == [] and p.refuse is None


# ---- geometry ----------------------------------------------------------------------------------------------
def tilted(det_text_pairs):
    """Two detections on one tilted line (about 3 degrees), the second holding a date."""
    toks, x = [], 10
    for i, t in enumerate(det_text_pairs):
        w = 200
        dy = int(0.05 * x)
        toks.append({"text": t, "conf": 0.99, "id": i, "line": 1,
                     "box": [[x, 110 + dy], [x + w, 120 + dy], [x + w, 160 + dy], [x, 150 + dy]]})
        x += w + 8
    return toks


def test_fill_never_covers_a_protected_quad_on_a_tilted_line():
    toks = tilted(["Cashier:", "ALEX", "25/03/2018"])
    base = rec()["tokens"]
    for k, t in enumerate(toks):
        t["id"] = len(base) + k
    r = {"lines": [], "tokens": base + toks}
    p = mask.plan_mask(r, SIDE, True, "M1")
    alex = [t["id"] for t in toks if t["text"] == "ALEX"][0]
    date = [t for t in toks if t["text"] == "25/03/2018"][0]
    assert p.hide == [alex] and p.refuse is None
    from PIL import Image
    img = Image.new("RGB", (900, 1300), (0, 0, 0))
    out, fill = mask.render(img, p, r, SIDE)
    m = mask.fill_mask(list(fill["polygons"].values()), [mask._quad(date)], (0, 0, 900, 1300))
    assert m.any() and not (m & mask.raster([mask._quad(date)], (0, 0, 900, 1300))).any()
    arr = np.array(out)
    assert (arr[m] != 0).any()                          # something was painted inside the fill


def test_overlapping_quads_refuse():
    r = rec(["Cashier:", "ALEX", "25/03/2018"])
    alex = next(t for t in r["tokens"] if t["text"] == "ALEX")
    date = next(t for t in r["tokens"] if t["text"] == "25/03/2018" and t["line"] == alex["line"])
    date["box"] = [[alex["box"][1][0] - 5, y] if k in (0, 3) else [x, y] for k, (x, y) in enumerate(date["box"])]
    assert mask.plan_mask(r, SIDE, True, "M1").refuse == "overlap_protected"


def test_expand_quad_moves_corners_outward():
    q = [(0, 0), (100, 0), (100, 20), (0, 20)]
    e = mask.expand_quad(q, 2)
    assert e[0] == [-2.0, -2.0] and e[2] == [102.0, 22.0]


# ---- post-mask check, locate_gt, item_hidden ----------------------------------------------------------------
def test_post_check_finds_a_readable_value_and_ignores_tags():
    _, p = texts_hidden(rec(["Cashier:ALEX"]))
    leak = mask.post_check("x.png", p, ocr=lambda _: {"tokens": [{"text": "Cash ier: AL EX"}]})
    clean = mask.post_check("x.png", p, ocr=lambda _: {"tokens": [{"text": "[P1]"}, {"text": "TOTAL 26.50"}]})
    assert not leak["ok"] and clean["ok"]


def test_locate_gt():
    dets = [{"id": 0, "text": "DATE:25/03/2018"}, {"id": 1, "text": "9555012503201812"},
            {"id": 2, "text": "RM26.50"}, {"id": 3, "text": "126.50"}, {"id": 4, "text": "25 MAR 18"}]
    loc = mask.locate_gt(dets, {"date": "2018-03-25", "total": 26.5})
    assert loc["date"] == [0, 4] and loc["total"] == [2]
    assert mask.locate_gt(dets, {"date": "2019-01-02", "total": None}) == {"date": [], "total": None}


def test_item_hidden_by_ids_and_by_coverage():
    mm = {"hide": [3], "rows": [{"fill": [[0, 0], [100, 0], [100, 20], [0, 20]]}], "protected_quads": {}}
    assert mask.item_hidden({"detection_ids": [3]}, mm) == (True, "ids")
    assert mask.item_hidden({"detection_ids": []}, mm) == (False, "ids")
    assert mask.item_hidden({"box": [[10, 2], [90, 2], [90, 18], [10, 18]]}, mm) == (True, "coverage")
    assert mask.item_hidden({"box": [[50, 2], [190, 2], [190, 18], [50, 18]]}, mm)[0] is False


# ---- labels -------------------------------------------------------------------------------------------------
def test_labels_validate_and_hash(tmp_path):
    r = rec(["Cashier:ALEX"])
    ok, data, warn = mask.validate_labels({"items": [{"category": "staff_name", "text": "ALEX", "detection_ids": [2]}]},
                                          n_detections=len(r["tokens"]))
    assert ok and data["items"][0]["detection_ids"] == [2] and not warn
    bad, _, warn = mask.validate_labels({"items": [{"category": "shop_name", "text": "X", "detection_ids": [99]}]}, 12)
    assert not bad and len(warn) == 2
    lab = {"format_version": 1, "receipt": "k", "labeler": "test", "status": "valid",
           "detections_sha256": mask.detections_sha256(r["tokens"]), "items": data["items"]}
    p = tmp_path / "k.json"
    p.write_text(json.dumps(lab), encoding="utf-8")
    assert mask.load_labels(p, r["tokens"])["items"]
    r["tokens"][0]["text"] = "changed"
    with pytest.raises(ValueError):
        mask.load_labels(p, r["tokens"])


def test_label_prompt_lists_every_detection_and_category():
    r = rec(["Cashier:ALEX"])
    txt = mask.label_prompt(r["tokens"])
    assert all(f"{d['id']}: {d['text']}" in txt for d in r["tokens"]) and all(c in txt for c in mask.CATEGORIES)
    assert set(mask.LABEL_SCHEMA["properties"]["items"]["items"]["properties"]["category"]["enum"]) == set(mask.CATEGORIES)


# ---- sidecars, dev set, provenance --------------------------------------------------------------------------
def test_sidecars_load_and_publish_full():
    for ds in ("sroie300", "wild200"):
        s = mask.load_sidecar(ROOT / "data" / "manifest" / f"{ds}.mask.json")
        assert s["publish_reads"] == "full" and s["pad"]["min_px"] == 2


def test_cited_receipts_are_dev_receipts():
    for res, key in CITED:
        s = json.loads((ROOT / res / "pii" / "sample.json").read_text(encoding="utf-8"))
        assert key in s["dev_keys"] and key not in s["keys"], key


def test_provenance_lists_the_frozen_modules_from_a_fresh_interpreter():
    mods = mask.provenance_modules()
    for m in ("src/harness/mask.py", "src/harness/pii_run.py", "src/harness/engines/vlm.py",
              "src/harness/engines/traditional.py", "src/harness/rules.py", "src/harness/verify.py"):
        assert m in mods, m
    import harness.scoring  # noqa: F401  (loading more modules here must not change the answer)
    assert mask.provenance_modules() == mods
    prov = mask.code_provenance([ROOT / "data" / "manifest" / "sroie300.mask.json"], modules=mods)
    assert prov["new_modules"] == [] and all(prov["modules"].values())
