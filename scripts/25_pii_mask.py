"""25_pii_mask.py - the masking experiment's commands (plan: docs/plan-pii-mask.md, "Order and budget").

Wiring only: every decision lives in src/harness/mask.py and src/harness/pii_run.py, which are frozen before
any label is requested. Every subcommand takes --results, --manifest and --run (default r0) and runs from
the repository root. Steps add their subcommands as they are built:

    freeze   (step 2)  record the code provenance of mask.py and pii_run.py in results*/pii/<run>/freeze.json
    label    (step 3)  Gemini 3.1 Flash-Lite labels the personal data on each sampled receipt (paid calls;
                       local labels under data/raw/pii_local/<dataset>/labels/); --dry-run sends nothing
    mask     (step 4)  U, M1, M2 images, mask maps, post-mask check, the Gate; plans the T3 jobs; lists the
                       M1 receipts whose ground truth could not be located (hand check, step 4b)
    read     (step 5)  Flash-Lite reads every planned U, M1, M2 image (paid calls)
    replay   (step 6a, 6c)  04_harness.py on one variant, arguments from pii_paths
    t4       (step 6b) 3.6 Flash reads the U and M1 images whose T3 answer the replay flagged (paid calls)
    summary  (step 7)  criteria, metrics and the verdict into results*/harness/pii.json (--replay-only: the
                       committed-files part, for run_all.py)

    python scripts/25_pii_mask.py freeze --results results --manifest data/manifest/sroie300.jsonl
    python scripts/25_pii_mask.py label --results results --manifest data/manifest/sroie300.jsonl --dry-run
    python scripts/25_pii_mask.py label --results results_wild --manifest data/manifest/wild200.jsonl [--limit 1]
    python scripts/25_pii_mask.py replay --results results --manifest data/manifest/sroie300.jsonl --variant M1

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


# ---------------------------------------------------------------------------
# Steps 4-7
# ---------------------------------------------------------------------------
def sample_keys(P: dict) -> list[str]:
    return json.loads(P["sample"].read_text(encoding="utf-8"))["keys"]


def mask_maps(P: dict, variant: str) -> dict:
    out = {}
    for k in sample_keys(P):
        f = P["mask_maps"] / f"{k}.{variant}.json"
        if f.exists():
            out[k] = json.loads(f.read_text(encoding="utf-8"))
    return out


def run_variants(P: dict) -> tuple:
    """r0 runs U, M1, M2; a revision runs U (reused from r0) and M1 only."""
    return mask.VARIANTS if P["run"] == "r0" else ("U", "M1")


def refresh_views(P: dict, table: pii_run.JobTable) -> None:
    keys = sample_keys(P)
    for v in run_variants(P):
        mm = mask_maps(P, v)
        pii_run.write_jobs_view(P, v, keys, table, {k: m["n_tags"] for k, m in mm.items()},
                                {k for k, m in mm.items() if m["refuse"]})


def cmd_mask(P: dict, args) -> None:
    require_frozen(P)
    side = mask.load_sidecar(P["sidecar"])
    mode = side.get("modes", {}).get(P["run"], "labels")
    man = manifest_map(P)
    table = pii_run.JobTable(P["job_table"])
    reasons: dict = {}
    unknown = []
    for i, k in enumerate(sample_keys(P), 1):
        rec = json.loads((P["boxes"] / f"{k}.json").read_text(encoding="utf-8"))
        df = man[k].get("day_first", True)
        for v in run_variants(P):
            mf = P["mask_maps"] / f"{k}.{v}.json"
            if mf.exists():
                continue
            plan = mask.plan_mask(rec, side, df, v, mode=mode)
            payload_sha, post = None, None
            if plan.refuse is None:
                img, fill = mask.render(ROOT / man[k]["image"], plan, rec, side)
                path = mask.save_image(img, P["images"] / f"{k}.{v}.png")
                data, mime = vlm.payload_bytes(path)
                payload_sha = hashlib.sha256(data).hexdigest()
                if v != "U":                            # U hides nothing: nothing to look for
                    po = P["post_ocr"] / f"{k}.{v}.{'jpg' if mime == 'image/jpeg' else 'png'}"
                    po.parent.mkdir(parents=True, exist_ok=True)
                    po.write_bytes(data)
                    post = mask.post_check(po, plan)
                    if not post["ok"]:
                        plan.refuse = "post_check"
                        path.unlink()
                        payload_sha = None
            else:
                fill = {"polygons": {}, "sha256": None}
            mm = mask.mask_map(plan, rec, fill, P["run"], k, payload_sha)
            mm["post_check"] = post
            mf.parent.mkdir(parents=True, exist_ok=True)
            mf.write_text(json.dumps(mm, ensure_ascii=False, indent=1), encoding="utf-8")
            job = table.new_attempt(P["run"], P["dataset"], k, v, "t3", payload_sha)
            if plan.refuse:
                table.mark(job, "refused", reason=plan.refuse)
                reasons.setdefault(v, {}).setdefault(plan.refuse, 0)
                reasons[v][plan.refuse] += 1
            if v == "M1" and plan.refuse is None:
                loc = mask.locate_gt(rec["tokens"], man[k]["gt"])
                if any(loc[f] == [] for f in ("date", "total")):
                    unknown.append(k)
        print(f"[{i}/30] {k}", flush=True)
    refresh_views(P, table)
    print(f"{P['dataset']} {P['run']} (mode {mode}): Gate refusals {reasons or 0}")
    print(f"  M1 receipts where the ground truth could not be located (hand check, step 4b): {len(unknown)} {unknown}")


def cmd_read(P: dict, args, tier: str = "t3") -> None:
    require_frozen(P)
    table = pii_run.JobTable(P["job_table"])
    if table.recover():
        print("  recovered interrupted jobs as failed")
    engine = "gemini-lite" if tier == "t3" else "gemini"
    prompt = vlm.extraction_prompt()
    bound = pii_run.input_bound(P["results"], engine, prompt)
    b = pii_run.Budget(P["budget"])
    b.open(P["run"])
    keys = sample_keys(P)
    if tier == "t4":
        todo = t4_selection(P, table)
    else:
        todo = []
        for v in run_variants(P):
            for k in keys:
                last = table.latest(P["run"], P["dataset"], k, v, "t3")
                if last and last["status"] == "planned" and not (P["variant"][v]["reads_t3"] / f"{k}.json").exists():
                    todo.append((k, v, last))
    print(f"{P['dataset']} {P['run']} {tier}: {len(todo)} reads to send; campaign spent ${b.spent():.4f}")
    stats = {"read": 0, "failed": 0}
    for k, v, job in todo:
        img = P["images"] / f"{k}.{v}.png"
        out = P["variant"][v]["reads_t3" if tier == "t3" else "reads_t4"] / f"{k}.json"
        reuse = table.reusable(P["dataset"], k, "U", tier, job["payload_sha256"]) if v == "U" and P["run"] != "r0" else None
        if reuse:   # a revision reuses r0's U read of the same bytes: no call
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes((ROOT / reuse["read_path"]).read_bytes())
            table.mark(job, "done", read_path=out.relative_to(ROOT).as_posix(), reason=f"reused {reuse['run']}")
            stats.setdefault("reused", 0)
            stats["reused"] += 1
            continue
        n = 0
        while True:
            n += 1

            def store(r, k=k, out=out):
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps({**r, "key": k}, ensure_ascii=False, indent=1), encoding="utf-8")
                return out.relative_to(ROOT).as_posix()
            try:
                r = pii_run.send(table, job, img, engine, b, bound, store)
            except (pii_run.NotSendable, pii_run.BudgetExceeded, vlm.SpendCapReached) as exc:
                print(f"  stop at {k} {v}: {type(exc).__name__}: {exc}")
                refresh_views(P, table)
                return
            if r is not None or n >= 2:
                break
            job = table.new_attempt(P["run"], P["dataset"], k, v, tier, job["payload_sha256"])
        stats["read" if r is not None else "failed"] += 1
    refresh_views(P, table)
    print(f"  done: {stats}; campaign spent ${b.spent():.4f}, reserved ${b.state()['reserved_usd']:.4f}")


def t4_selection(P: dict, table: pii_run.JobTable) -> list:
    """6b: U and M1 receipts whose T3 read exists and whose replay flags are real; the others get not_needed."""
    todo = []
    for v in ("U", "M1"):
        view = json.loads(P["variant"][v]["jobs_json"].read_text(encoding="utf-8"))["receipts"]
        rows = {}
        with (P["variant"][v]["harness"] / "per_receipt.jsonl").open(encoding="utf-8") as fh:
            for l in fh:
                if l.strip():
                    r = json.loads(l)
                    rows[r["key"]] = r
        for k, j in sorted(view.items()):
            if j["t3"] != "read" or j["t4"] in ("read", "not_needed"):
                continue
            flags = [f for f in rows[k]["flags"]["t3"] if f != "UNAVAILABLE"]
            t3job = table.latest(P["run"], P["dataset"], k, v, "t3")
            if flags:
                last = table.latest(P["run"], P["dataset"], k, v, "t4")
                job = last if last and last["status"] == "planned" else \
                    table.new_attempt(P["run"], P["dataset"], k, v, "t4", t3job["payload_sha256"])
                todo.append((k, v, job))
            else:
                table.mark(table.new_attempt(P["run"], P["dataset"], k, v, "t4", t3job["payload_sha256"]), "not_needed")
    refresh_views(P, table)
    return todo


def cmd_t4(P: dict, args) -> None:
    cmd_read(P, args, tier="t4")


def cmd_replay(P: dict, args) -> None:
    import subprocess
    variants = [args.variant] if args.variant else ["U", "M1"]
    for v in variants:
        cmd = [sys.executable, str(ROOT / "scripts" / "04_harness.py")] + pii_run.replay_args(P, v)
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if out.returncode != 0:
            raise SystemExit(f"replay {v} failed:\n{out.stdout[-800:]}\n{out.stderr[-800:]}")
        print(f"{P['dataset']} {P['run']} replay {v}: {out.stdout.strip().splitlines()[-1]}")


def _provenance_now(P: dict) -> dict:
    frozen = json.loads(P["freeze"].read_text(encoding="utf-8"))["provenance"]
    now = mask.code_provenance([P["sidecar"]], modules=list(frozen["modules"]))
    return {"frozen": frozen, "current": now,
            "revised": now["modules"] != frozen["modules"] or now["sidecars"] != frozen["sidecars"]}


def replay_part(P: dict, man: dict) -> dict:
    keys = sample_keys(P)
    cmd_replay(P, argparse.Namespace(variant=None))
    files = [P["manifest"] if P["manifest"].is_absolute() else ROOT / P["manifest"]]
    for v in mask.VARIANTS:
        vv = P["variant"][v]
        files.append(vv["jobs_json"])
        files += [vv["reads_t3"] / f"{k}.json" for k in keys] + [vv["reads_t4"] / f"{k}.json" for k in keys]
    files += [P["results"] / e / f"{k}.json" for e in ("rapidocr", "tesseract") for k in keys]
    prov = _provenance_now(P)
    prov["routing"] = {f: pii_run.sha256_file(ROOT / f) for f in ("scripts/04_harness.py",)}
    return {"provenance": prov, "inputs": pii_run.inputs_sha256(files),
            "models": {"t3": vlm.ENGINE_CHAINS["gemini-lite"][0][1], "t4": vlm.ENGINE_CHAINS["gemini"][0][1]},
            P["dataset"]: pii_run.metrics_replay(P, keys, man)}


def cmd_summary(P: dict, args) -> None:
    man = manifest_map(P)
    keys = sample_keys(P)
    rep = replay_part(P, man)
    pii_run.write_pii_json(P, P["run"], "replay", rep)
    print(json.dumps(rep[P["dataset"]], indent=1)[:1500])
    if args.replay_only:
        return
    files = [P["boxes"] / f"{k}.json" for k in keys] + [P["labels"] / f"{k}.json" for k in keys]
    files += [P["mask_maps"] / f"{k}.{v}.json" for k in keys for v in mask.VARIANTS] + [P["job_table"], P["gt_checks"]]
    loc = pii_run.metrics_local(P, keys, man)
    loc["verdict"] = pii_run.verdict(rep[P["dataset"]], loc)
    prov = _provenance_now(P)
    part = {"provenance": prov, "inputs": {k: v for k, v in pii_run.inputs_sha256(files).items()},
            "inputs_checked": True, "revised": prov["revised"], P["dataset"]: loc}
    pii_run.write_pii_json(P, P["run"], "local", part)
    print(json.dumps(loc, indent=1)[:2500])


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
    cmds = {"freeze": cmd_freeze, "label": cmd_label, "mask": cmd_mask, "read": cmd_read, "replay": cmd_replay,
            "t4": cmd_t4, "summary": cmd_summary}
    for name in cmds:
        s = sub.add_parser(name)
        s.add_argument("--results", required=True)
        s.add_argument("--manifest", required=True)
        s.add_argument("--run", default="r0")
        if name == "label":
            s.add_argument("--dry-run", action="store_true", help="list what would be sent and the cost; send nothing")
            s.add_argument("--limit", type=int, default=0, help="send at most this many receipts")
        if name == "replay":
            s.add_argument("--variant", choices=["U", "M1"], default=None, help="default: both")
        if name == "summary":
            s.add_argument("--replay-only", action="store_true", help="only the part computed from committed files")
    args = ap.parse_args()
    P = mask.pii_paths(ROOT / args.results, ROOT / args.manifest, run=args.run)
    cmds[args.cmd](P, args)


if __name__ == "__main__":
    main()
