"""25_pii_mask.py - the masking experiment's commands (plan: docs/plan-pii-mask.md, "Order and budget").

Wiring only: every decision lives in src/harness/mask.py and src/harness/pii_run.py, which are frozen before
any label is requested. Every subcommand takes --results, --manifest and --run (default r0) and runs from
the repository root. Steps add their subcommands as they are built:

    freeze   (step 2)  record the code provenance of mask.py and pii_run.py in results*/pii/<run>/freeze.json
    label    (step 3)  Gemini 3.1 Flash-Lite labels the personal data on each sampled receipt (paid calls;
                       local labels under data/raw/pii_local/<dataset>/labels/); --dry-run sends nothing

    python scripts/25_pii_mask.py freeze --results results --manifest data/manifest/sroie300.jsonl
    python scripts/25_pii_mask.py label --results results --manifest data/manifest/sroie300.jsonl --dry-run
    python scripts/25_pii_mask.py label --results results_wild --manifest data/manifest/wild200.jsonl [--limit 1]

A frozen run is never re-frozen with different code: a change after the freeze is a revision (--run rev1).
Paid subcommands refuse to run unless the run is frozen with the current code.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from harness import mask, pii_run  # noqa: E402
from harness.engines import vlm  # noqa: E402

LABEL_ENGINE = "gemini-lite"


def require_frozen(P: dict) -> None:
    """Paid steps run only on frozen code: freeze.json exists and the current code has the same hashes."""
    f = P["freeze"]
    if not f.exists():
        raise SystemExit(f"{P['dataset']} {P['run']} is not frozen: run 25_pii_mask.py freeze first")
    frozen = json.loads(f.read_text(encoding="utf-8"))["provenance"]
    now = mask.code_provenance([P["sidecar"]], modules=list(frozen["modules"]))
    if now["modules"] != frozen["modules"] or now["sidecars"] != frozen["sidecars"]:
        changed = sorted(k for k, v in now["modules"].items() if frozen["modules"].get(k) != v)
        raise SystemExit(f"code changed since the freeze ({changed or 'sidecar'}): that is a revision (--run rev<k>)")


def manifest_map(P: dict) -> dict:
    with open(ROOT / P["manifest"], encoding="utf-8") as fh:
        return {m["key"]: m for m in (json.loads(l) for l in fh if l.strip())}


def cmd_label(P: dict, args) -> None:
    require_frozen(P)
    keys = json.loads(P["sample"].read_text(encoding="utf-8"))["keys"]
    man = manifest_map(P)
    model = vlm.ENGINE_CHAINS[LABEL_ENGINE][0][1]
    todo = []
    for k in keys:
        if (P["labels"] / f"{k}.json").exists():
            continue
        rec = json.loads((P["boxes"] / f"{k}.json").read_text(encoding="utf-8"))
        prompt = mask.label_prompt(rec["tokens"])
        img = ROOT / man[k]["image"]
        data, _ = vlm.payload_bytes(img)
        todo.append({"key": k, "tokens": rec["tokens"], "prompt": prompt, "image": img,
                     "sha": hashlib.sha256(data).hexdigest(),
                     "bound": pii_run.input_bound(P["results"], LABEL_ENGINE, prompt)})
    if args.limit:
        todo = todo[: args.limit]
    # Expected cost: the benchmark's median image input for this engine, the prompt at ~4 characters a token,
    # and a short answer; the budget reserves the maximum per request instead.
    ins = [int((json.loads(f.read_text(encoding="utf-8")).get("usage") or {}).get("input_tokens") or 0)
           for f in (P["results"] / LABEL_ENGINE).glob("*.json")]
    med = statistics.median([i for i in ins if i]) if ins else 0
    exp = [vlm._cost(model, int(med + len(t["prompt"]) / 4), 300) for t in todo]   # med already holds a prompt: cautious
    mx = [vlm.max_request_usd(model, t["bound"]) for t in todo]
    done = sum(1 for k in keys if (P["labels"] / f"{k}.json").exists())
    print(f"{P['dataset']} {P['run']}: {done} of {len(keys)} already labeled; to send now {len(todo)} label calls to {model}")
    print(f"  expected about ${sum(exp):.4f} in all (median ${statistics.median(exp) if exp else 0:.5f} each); "
          f"the budget reserves up to ${max(mx) if mx else 0:.5f} per request while it is in flight")
    b = pii_run.Budget(P["budget"])
    if P["budget"].exists() and pii_run.CAMPAIGN in json.loads(P["budget"].read_text(encoding="utf-8"))["campaigns"]:
        st = b.state()
        print(f"  campaign {pii_run.CAMPAIGN}: spent ${b.spent():.4f}, reserved ${st['reserved_usd']:.4f}, "
              f"allowance ${st['allowance_usd']:.2f}")
    else:
        print(f"  campaign {pii_run.CAMPAIGN} not opened yet: the first paid call fixes cap_base at the ledger total "
              f"(now ${vlm.spend_total():.4f}) and allows ${pii_run.ALLOWANCE_USD:.2f} on top")
    if args.dry_run or not todo:
        print("  dry run: nothing sent" if args.dry_run else "  nothing to send")
        return

    table = pii_run.JobTable(P["job_table"])
    if table.recover():
        print("  recovered interrupted jobs as failed")
    b.open(P["run"])
    stats = {"valid": 0, "invalid": 0, "missing": 0}
    for t in todo:
        validate = functools.partial(mask.validate_labels, n_detections=len(t["tokens"]))
        result, n_sent, reask = None, 0, False
        while True:
            job = table.new_attempt(P["run"], P["dataset"], t["key"], "U", "label", t["sha"], reask=reask)

            def store(r, k=t["key"], a=job["attempt"]):
                p = P["labels"] / "raw" / f"{k}.a{a}.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
                return p.relative_to(ROOT).as_posix()
            try:
                r = pii_run.send(table, job, t["image"], LABEL_ENGINE, b, t["bound"], store, prompt=t["prompt"],
                                 schema=mask.LABEL_SCHEMA, validate=validate)
            except (pii_run.NotSendable, pii_run.BudgetExceeded, vlm.SpendCapReached) as exc:
                print(f"  stop at {t['key']}: {type(exc).__name__}: {exc}")
                print(f"  {stats}; campaign spent ${b.spent():.4f}, reserved ${b.state()['reserved_usd']:.4f}")
                return
            n_sent += 1
            ok = r is not None and (r.get("sanitizer") or {}).get("is_safe") is True and isinstance(r.get("data"), dict)
            if ok:
                result = r
                break
            if r is not None and not reask:          # an invalid answer: one re-ask
                reask = True
                continue
            if r is None and n_sent < 2:             # the provider failed: one more attempt
                continue
            result = r
            break
        lab = {"format_version": 1, "receipt": t["key"], "labeler": model,
               "detections_sha256": mask.detections_sha256(t["tokens"]),
               "status": "valid" if result is not None and (result.get("sanitizer") or {}).get("is_safe") is True else "invalid",
               "items": (result.get("data") or {}).get("items", []) if result is not None else [],
               "warnings": (result.get("sanitizer") or {}).get("warnings", []) if result is not None else ["no answer"],
               "requests": n_sent}
        if result is None:
            stats["missing"] += 1
        else:
            stats[lab["status"]] += 1
        P["labels"].mkdir(parents=True, exist_ok=True)
        (P["labels"] / f"{t['key']}.json").write_text(json.dumps(lab, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {t['key']}: {lab['status']}, {len(lab['items'])} items, {n_sent} request(s)", flush=True)
    print(f"  done: {stats}; campaign spent ${b.spent():.4f}, reserved ${b.state()['reserved_usd']:.4f}")


def cmd_freeze(P: dict, args) -> None:
    prov = mask.code_provenance([P["sidecar"]])
    if prov["new_modules"]:
        raise SystemExit(f"unexpected modules {prov['new_modules']}")
    doc = {"format_version": 1, "run": P["run"], "dataset": P["dataset"], "frozen": date.today().isoformat(),
           "plan": "docs/plan-pii-mask.md", "provenance": prov}
    f = P["freeze"]
    if f.exists():
        old = json.loads(f.read_text(encoding="utf-8"))
        if old["provenance"] == prov:
            print(f"{f.relative_to(ROOT).as_posix()}: already frozen with the same code ({old['frozen']})")
            return
        changed = sorted(k for k, v in prov["modules"].items() if old["provenance"]["modules"].get(k) != v)
        raise SystemExit(f"{f.relative_to(ROOT).as_posix()} is frozen with other code (changed: {changed}); "
                         f"a change after the freeze is a revision: use --run rev<k>")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"froze {P['dataset']} {P['run']}: {len(prov['modules'])} modules, sidecar "
          f"{next(iter(prov['sidecars']))}, -> {f.relative_to(ROOT).as_posix()}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("freeze", "label"):
        s = sub.add_parser(name)
        s.add_argument("--results", required=True)
        s.add_argument("--manifest", required=True)
        s.add_argument("--run", default="r0")
        if name == "label":
            s.add_argument("--dry-run", action="store_true", help="list what would be sent and the cost; send nothing")
            s.add_argument("--limit", type=int, default=0, help="send at most this many receipts")
    args = ap.parse_args()
    P = mask.pii_paths(ROOT / args.results, ROOT / args.manifest, run=args.run)
    {"freeze": cmd_freeze, "label": cmd_label}[args.cmd](P, args)


if __name__ == "__main__":
    main()
