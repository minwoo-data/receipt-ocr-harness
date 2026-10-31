"""01_fetch_sroie.py - Download SROIE (CC-BY-4.0), extract images, build the
300-receipt evaluation manifest with normalized ground truth.

Usage:
    python scripts/01_fetch_sroie.py            # 300-receipt sample, seed 20261031
    python scripts/01_fetch_sroie.py --n 50     # smaller smoke sample

Outputs (data/raw is git-ignored, data/manifest is committed):
    data/raw/sroie/{train,test}.parquet          (downloaded if missing)
    data/raw/sroie/images/<key>.jpg              (one file per sampled receipt)
    data/manifest/sroie300.jsonl                 (key, split, image path, gt_raw, gt)
    data/manifest/sroie300_report.md             (how many GT fields normalized)

Source: jsdnrs/ICDAR2019-SROIE on Hugging Face (ICDAR 2019 SROIE, Huang et al.).
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from harness.normalize import norm_company, norm_date, norm_total  # noqa: E402

RAW = ROOT / "data" / "raw" / "sroie"
IMAGES = RAW / "images"
MANIFEST_DIR = ROOT / "data" / "manifest"
HF_REPO = "jsdnrs/ICDAR2019-SROIE"
FILES = {"train": "data/train-00000-of-00001.parquet",
         "test": "data/test-00000-of-00001.parquet"}


def ensure_downloaded() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    missing = [s for s in FILES if not (RAW / f"{s}.parquet").exists()]
    if not missing:
        return
    from huggingface_hub import hf_hub_download
    for split in missing:
        path = hf_hub_download(HF_REPO, FILES[split], repo_type="dataset")
        (RAW / f"{split}.parquet").write_bytes(Path(path).read_bytes())
        print(f"downloaded {split}.parquet")


def load_rows() -> list[dict]:
    rows: list[dict] = []
    for split in FILES:
        table = pq.read_table(RAW / f"{split}.parquet",
                              columns=["image", "key", "entities"])
        for rec in table.to_pylist():
            ent = rec["entities"] or {}
            rows.append({
                "key": rec["key"],
                "split": split,
                "image_bytes": rec["image"]["bytes"],
                "gt_raw": {k: ent.get(k) for k in ("company", "date", "address", "total")},
            })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20261031)
    ap.add_argument("--name", default="sroie300")
    args = ap.parse_args()

    ensure_downloaded()
    rows = load_rows()
    print(f"total receipts available: {len(rows)}")

    rng = random.Random(args.seed)
    rows.sort(key=lambda r: r["key"])          # deterministic before shuffle
    rng.shuffle(rows)
    sample = rows[: args.n]

    IMAGES.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    out = MANIFEST_DIR / f"{args.name}.jsonl"
    stats = {"company": 0, "date": 0, "total": 0, "date_unparsed": []}

    with out.open("w", encoding="utf-8") as fh:
        for r in sample:
            img_path = IMAGES / f"{r['key']}.jpg"
            if not img_path.exists():
                Image.open(io.BytesIO(r["image_bytes"])).convert("RGB").save(img_path, "JPEG", quality=95)
            gt = {
                "company": norm_company(r["gt_raw"]["company"]),
                "date": norm_date(r["gt_raw"]["date"], day_first=True),
                "total": norm_total(r["gt_raw"]["total"]),
            }
            for k in ("company", "date", "total"):
                if gt[k] is not None:
                    stats[k] += 1
            if gt["date"] is None:
                stats["date_unparsed"].append((r["key"], r["gt_raw"]["date"]))
            fh.write(json.dumps({
                "key": r["key"],
                "split": r["split"],
                "image": str(img_path.relative_to(ROOT)).replace("\\", "/"),
                "gt_raw": r["gt_raw"],
                "gt": gt,
            }, ensure_ascii=False) + "\n")

    n = len(sample)
    report = [
        f"# {args.name} manifest report",
        "",
        f"- receipts sampled: {n} of {len(rows)} (seed {args.seed})",
        f"- ground truth normalized: company {stats['company']}/{n}, "
        f"date {stats['date']}/{n}, total {stats['total']}/{n}",
        "",
        "## GT dates the normalizer could not parse (fix normalizer or exclude)",
        "",
    ]
    report += [f"- {k}: `{v}`" for k, v in stats["date_unparsed"]] or ["- none"]
    (MANIFEST_DIR / f"{args.name}_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
