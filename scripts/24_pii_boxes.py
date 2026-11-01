"""24_pii_boxes.py - re-read a sample of receipts with RapidOCR, keeping where each piece of text sits.

The masking experiment (docs/plan-pii-mask.md) needs the box, id and line of every detection; the
tier-1 cache from the benchmark run kept only text and confidence. The sample is drawn from the
receipts the harness actually sends to the cloud (image reached T3 or T4, tau 0.9), because that is the
only place masking would run. Seed 20261031.

    python scripts/24_pii_boxes.py --results results --manifest data/manifest/sroie300.jsonl
    python scripts/24_pii_boxes.py --results results_wild --manifest data/manifest/wild200.jsonl [--force]

Writes <results>/pii/sample.json (committed: the keys and how they were drawn) and the run_rapidocr
records, whose tokens carry "box", "id" and "line", under data/raw/pii_local/<dataset>/boxes/ (local
only: it holds the OCR text of every detection). Resumable; --force re-reads every sampled receipt.
Each re-read is compared with the cached read the harness used (tokens and lines), so a difference is
visible instead of silently changing the input. RapidOCR is a heavy local job: run one at a time.
"""
import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from harness.engines.traditional import run_rapidocr  # noqa: E402
from harness.mask import pii_paths  # noqa: E402

_spec = importlib.util.spec_from_file_location("harness04", ROOT / "scripts" / "04_harness.py")
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)

SEED = 20261031
TAU = 0.9


def cloud_bound(results: Path) -> tuple[list[str], int]:
    with (results / "harness" / "per_receipt.jsonl").open(encoding="utf-8") as fh:
        rows = [json.loads(l) for l in fh if l.strip()]
    keys = [r["key"] for r in rows if any(t in ("T3", "T4") for t in H.decide(r, "harness", {"tau": TAU})["path"])]
    return sorted(keys), len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--force", action="store_true", help="re-read receipts that already have a boxes record")
    args = ap.parse_args()
    results = ROOT / args.results
    P = pii_paths(results, args.manifest)
    P["public"].mkdir(parents=True, exist_ok=True)
    P["boxes"].mkdir(parents=True, exist_ok=True)

    pool, n_all = cloud_bound(results)
    if P["sample"].exists():
        sample = json.loads(P["sample"].read_text(encoding="utf-8"))
        assert sample["seed"] == SEED and sample["n"] == args.n and sample["pool"] == len(pool), "sample.json is from another draw"
        pick = sample["keys"]
    else:
        pick = sorted(random.Random(SEED).sample(pool, args.n))
        sample = {"seed": SEED, "n": args.n, "policy": "harness", "tau": TAU,
                  "drawn_from": "receipts whose image reached T3 or T4 under the harness policy",
                  "pool": len(pool), "receipts": n_all, "keys": pick}
        P["sample"].write_text(json.dumps(sample, indent=1), encoding="utf-8")
    print(f"{args.results}: {len(pool)} of {n_all} receipts go to the cloud; sample {len(pick)}", flush=True)

    with open(ROOT / args.manifest, encoding="utf-8") as fh:
        manifest = {m["key"]: m for m in (json.loads(l) for l in fh if l.strip())}
    for i, k in enumerate(pick, 1):
        dst = P["boxes"] / f"{k}.json"
        if dst.exists() and not args.force:
            continue
        rec = run_rapidocr(ROOT / manifest[k]["image"])
        cached = json.loads((results / "rapidocr" / f"{k}.json").read_text(encoding="utf-8"))
        rec["key"] = k
        rec["image"] = manifest[k]["image"]
        rec["same_text_as_cache"] = ([t["text"] for t in rec["tokens"]] == [t["text"] for t in cached["tokens"]]
                                     and rec["lines"] == cached["lines"])
        dst.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        print(f"[{i}/{len(pick)}] {k} tokens={len(rec['tokens'])} same_text={rec['same_text_as_cache']}", flush=True)

    recs = [json.loads((P["boxes"] / f"{k}.json").read_text(encoding="utf-8")) for k in pick]
    diff = [r["key"] for r in recs if not r["same_text_as_cache"]]
    no_ids = [r["key"] for r in recs if any("id" not in t or "line" not in t for t in r["tokens"])]
    print(f"done: {len(recs)} receipts with boxes; differs from the cached read on {len(diff)} {diff}; "
          f"missing id/line on {len(no_ids)}", flush=True)
    if diff or no_ids:
        sys.exit("stop: find out why before step 2 (docs/plan-pii-mask.md, step 1b)")


if __name__ == "__main__":
    main()
