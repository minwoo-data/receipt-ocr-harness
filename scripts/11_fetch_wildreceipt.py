"""11_fetch_wildreceipt.py - Build the 200-receipt WildReceipt evaluation manifest.

WildReceipt (Sun et al., arXiv:2103.14470; distributed by OpenMMLab) holds
about 1,740 photographed receipts, mostly English, from many countries, with
word-level boxes labelled by key (Store_name_value=1, Date_value=7,
Total_value=23, ...). Ground truth for our three fields is the concatenation
of the words carrying each value label, in reading order.

Why a filter on dates: the receipts mix US (month-first) and UK/AU (day-first)
conventions and the dataset does not say which. A receipt is kept only when
its printed date is unambiguous (a textual month, or a day > 12), so the
ground-truth date never depends on a guess. Receipts are read as month-first
(day_first = False) because US stores dominate the set.

Usage:
    python scripts/11_fetch_wildreceipt.py --n 200
Outputs:
    data/raw/wildreceipt/images/<id>.jpg   (copied from the extracted tar)
    data/manifest/wild200.jsonl            (same shape as sroie300 + day_first flag)
    data/manifest/wild200_report.md
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from harness.normalize import norm_company, norm_date, norm_total  # noqa: E402

RAW = ROOT / "data" / "raw" / "wildreceipt" / "wildreceipt"
IMAGES = ROOT / "data" / "raw" / "wildreceipt" / "images"
MANIFEST_DIR = ROOT / "data" / "manifest"
LABELS = {1: "company", 7: "date", 23: "total"}
_TEXT_MONTH = re.compile(r"[A-Za-z]{3,9}")
_NUMERIC = re.compile(r"(\d{1,4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{2,4})")


def unambiguous(date_text: str) -> bool:
    """True when the printed date cannot be read two ways."""
    if _TEXT_MONTH.search(date_text):
        return True
    m = _NUMERIC.search(date_text)
    if not m:
        return False
    a, b, c = m.groups()
    if len(a) == 4:                       # year first: unambiguous
        return True
    return int(a) > 12 or int(b) > 12     # one of the two must be a day


def field_text(ann: list[dict], label: int) -> str | None:
    words = [(a["box"][7] if len(a["box"]) == 8 else 0, a["box"][0], a["text"]) for a in ann if a.get("label") == label and a.get("text")]
    if not words:
        return None
    words.sort(key=lambda w: (round(w[0] / 15), w[1]))
    return " ".join(w[2] for w in words)


def renormalize(path: Path) -> None:
    """Re-derive gt from gt_raw with the current normalizer for the receipts already in the manifest.
    The sample is not redrawn: the held-out set stays the same 200 receipts."""
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    changed = []
    for r in rows:
        raw, df = r["gt_raw"], r.get("day_first", False)
        new = {"company": norm_company(raw["company"]), "date": norm_date(raw["date"], day_first=df), "total": norm_total(raw["total"])}
        for k in ("company", "date", "total"):
            if new[k] != r["gt"].get(k):
                changed.append((r["key"], k, r["gt"].get(k), new[k], raw[k]))
        r["gt"] = new
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    if changed:      # keep a record of every label that moved (read by report_numbers.py)
        from datetime import date as _date
        with path.with_name(path.stem + "_gt_corrections.jsonl").open("a", encoding="utf-8") as fh:
            for key, k, was, now, printed in changed:
                fh.write(json.dumps({"key": key, "field": k, "was": was, "now": now, "printed": printed,
                                     "date": _date.today().isoformat(), "cause": "normalizer change"}, ensure_ascii=False) + "\n")
    print(f"{path.name}: {len(changed)} ground-truth values changed")
    for c in changed:
        print("  {} {}: {!r} -> {!r} (printed {!r})".format(*c))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--renormalize", action="store_true",
                    help="only re-derive gt from gt_raw in the existing manifest (same receipts)")
    ap.add_argument("--seed", type=int, default=20261101)
    ap.add_argument("--name", default="wild200")
    args = ap.parse_args()
    if args.renormalize:
        renormalize(MANIFEST_DIR / f"{args.name}.jsonl")
        return

    rows = []
    for split in ("train", "test"):
        for line in (RAW / f"{split}.txt").open(encoding="utf-8"):
            if not line.strip():
                continue
            rec = json.loads(line)
            ann = rec.get("annotations") or []
            raw = {k: field_text(ann, lab) for lab, k in LABELS.items()}
            if not all(raw.values()):
                continue
            if not unambiguous(raw["date"]):
                continue
            gt = {"company": norm_company(raw["company"]),
                  "date": norm_date(raw["date"], day_first=False),
                  "total": norm_total(raw["total"])}
            if not all(gt.values()):
                continue
            rows.append({"file": rec["file_name"], "split": split, "gt_raw": raw, "gt": gt})
    print(f"eligible receipts (all three fields, unambiguous date): {len(rows)}")

    rng = random.Random(args.seed)
    rows.sort(key=lambda r: r["file"])
    rng.shuffle(rows)
    sample = rows[: args.n]
    IMAGES.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    out = MANIFEST_DIR / f"{args.name}.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for i, r in enumerate(sample, start=1):
            src = RAW / r["file"]
            key = f"W{i:04d}_{Path(r['file']).stem[:12]}"
            dst = IMAGES / f"{key}{src.suffix.lower()}"
            if not dst.exists():
                shutil.copy(src, dst)
            fh.write(json.dumps({
                "key": key, "split": r["split"], "image": str(dst.relative_to(ROOT)).replace("\\", "/"),
                "day_first": False, "gt_raw": r["gt_raw"], "gt": r["gt"],
            }, ensure_ascii=False) + "\n")
    report = [f"# {args.name} manifest report", "",
              f"- eligible: {len(rows)}; sampled: {len(sample)} (seed {args.seed})",
              "- date convention: month-first (day_first=false); only unambiguous printed dates were eligible",
              "- ground truth = concatenated words labelled Store_name_value / Date_value / Total_value", ""]
    (MANIFEST_DIR / f"{args.name}_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print("sample:", json.dumps(sample[0]["gt_raw"], ensure_ascii=False)[:200])


if __name__ == "__main__":
    main()
