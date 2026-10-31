"""02_run_engine.py - Run one reader over the manifest, one JSON per receipt.

Resumable: receipts that already have an output file are skipped, so a crash
or a rate limit never costs the work already done.

Usage:
    python scripts/02_run_engine.py --engine rapidocr
    python scripts/02_run_engine.py --engine tesseract
    python scripts/02_run_engine.py --engine qwen                 # Ollama qwen3-vl:2b (local)
    python scripts/02_run_engine.py --engine gemini-lite --workers 4   # gemini-3.1-flash-lite alone
    python scripts/02_run_engine.py --engine gemini --workers 4        # gemini-3.8-flash alone
    python scripts/02_run_engine.py --engine chain --workers 4         # lite -> 3.8 -> claude, fast-fail
    python scripts/02_run_engine.py --engine gemini --limit 10         # smoke test

Outputs: results/<engine>/<key>.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from harness import rules  # noqa: E402
from harness.engines import traditional  # noqa: E402

VLM_ENGINES = {
    "qwen": dict(kind="ollama", model="qwen2.5vl:3b"),
    "qwen3": dict(kind="ollama", model="qwen3-vl:2b"),
    "gemini": dict(kind="cloud", chain=(("gemini", "gemini-3.6-flash"),)),
    "gemini-38": dict(kind="cloud", chain=(("gemini", "gemini-3.8-flash"),)),
    "gemini-lite": dict(kind="cloud", chain=(("gemini", "gemini-3.1-flash-lite"),)),
    "gemini-lite35": dict(kind="cloud", chain=(("gemini", "gemini-3.5-flash-lite"),)),
    "claude": dict(kind="cloud", chain=(("claude", "claude-haiku-5-5"),)),
    "chain": dict(kind="cloud", chain=(("gemini", "gemini-3.1-flash-lite"),
                                       ("gemini", "gemini-3.6-flash"),
                                       ("claude", "claude-haiku-5-5"))),
}


def load_manifest(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def run_traditional(engine: str, item: dict) -> dict:
    out = traditional.ENGINES[engine](ROOT / item["image"])
    rr = rules.extract(out["lines"])
    out["fields"] = {"company": rr.company, "date": rr.date, "total": rr.total}
    out["rule_reasons"] = rr.reasons
    out["total_candidates"] = rr.total_candidates
    return out


def run_vlm(engine: str, item: dict) -> dict:
    from harness.engines import vlm
    spec = VLM_ENGINES[engine]
    if spec["kind"] == "ollama":
        return vlm.run_ollama(ROOT / item["image"], model=spec["model"])
    res = vlm.run_cloud_chain(ROOT / item["image"], chain=spec["chain"])
    if res.get("provider") == "none":
        # Infrastructure failure (no provider returned text): do not cache it as a
        # result, so the next run retries. A parse failure WITH text is kept: that
        # is a real model outcome worth counting.
        raise RuntimeError("all providers failed: " + json.dumps(res.get("attempts"))[:400])
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True,
                    choices=sorted(list(traditional.ENGINES) + list(VLM_ENGINES)))
    ap.add_argument("--manifest", default="data/manifest/sroie300.jsonl")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    items = load_manifest(ROOT / args.manifest)
    if args.limit:
        items = items[: args.limit]
    out_dir = ROOT / args.out / args.engine
    out_dir.mkdir(parents=True, exist_ok=True)

    todo = [it for it in items if not (out_dir / f"{it['key']}.json").exists()]
    print(f"{args.engine}: {len(items)} receipts, {len(todo)} to run, {len(items) - len(todo)} cached")

    runner = run_traditional if args.engine in traditional.ENGINES else run_vlm
    t0 = time.perf_counter()
    done = 0
    errors = 0

    def work(it: dict) -> tuple[str, dict | None, str | None]:
        try:
            return it["key"], runner(args.engine, it), None
        except Exception as exc:  # noqa: BLE001 - record and continue
            return it["key"], None, f"{type(exc).__name__}: {exc}"[:300]

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for key, result, err in (f.result() for f in as_completed(pool.submit(work, it) for it in todo)):
            if err:
                errors += 1
                print(f"  ERROR {key}: {err}")
                continue
            result["key"] = key
            (out_dir / f"{key}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(todo)} done, {time.perf_counter() - t0:.0f}s")

    print(f"{args.engine}: wrote {done}, errors {errors}, {time.perf_counter() - t0:.0f}s total")


if __name__ == "__main__":
    main()
