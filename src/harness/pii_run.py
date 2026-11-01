"""pii_run.py - running and judging the masking experiment (plan: docs/plan-pii-mask.md, "Running and judging").

Everything that decides whether an image leaves the machine, or whether a success criterion holds, lives here
or in mask.py, and both are frozen before any label is requested. scripts/25_pii_mask.py only loads files
and calls these functions.

    JobTable          append-only job table (local; request IDs never leave it)
    sendable          the last check before a request: not refused, one-model chain, payload unchanged
    Budget            per-request reservation against a campaign allowance (data/raw/pii_local/budget.json)
    send              one guarded request: sendable -> reserve -> sent -> call -> done / failed / planned
    jobs_view         the committed per-variant jobs.json, derived from the job table and the read files
    replay_args       04_harness.py arguments for one variant, built from pii_paths
    metrics_replay, metrics_local, verdict, write_pii_json
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from . import mask
from .bootstrap import paired_ci
from .engines import vlm
from .scoring import correct_fields, money_fields_ok, predicted_fields

ROOT = mask.ROOT
JOB_FORMAT = 1
CAMPAIGN = "booth-2026-11"
ALLOWANCE_USD = 0.20
REVIEW_LIMIT_POINTS = 5.0


class NotSendable(RuntimeError):
    """The request must not go out: refused receipt, a chain with more than one link, or changed bytes."""


class BudgetExceeded(RuntimeError):
    """This request does not fit in what is left of the campaign allowance."""


def _rel(p: str | Path) -> str:
    p = Path(p)
    return (p.resolve().relative_to(ROOT) if p.is_absolute() else p).as_posix()


def sha256_file(p: str | Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _dump(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# Job table
# ---------------------------------------------------------------------------
class JobTable:
    """Append-only jsonl; the last row per job key (run, dataset, receipt, variant, tier, attempt) is its state.
    Status: planned / sent / done / failed / refused / not_needed (t4 only: the replay did not flag it)."""

    KEY = ("run", "dataset", "receipt", "variant", "tier", "attempt")

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def append(self, **row) -> dict:
        row = {"format_version": JOB_FORMAT, **row}
        missing = [k for k in self.KEY if k not in row]
        if missing:
            raise ValueError(f"job row lacks {missing}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return row

    def history(self, run: str, dataset: str, receipt: str, variant: str, tier: str) -> list[dict]:
        return [r for r in self.rows() if (r["run"], r["dataset"], r["receipt"], r["variant"], r["tier"])
                == (run, dataset, receipt, variant, tier)]

    def latest(self, *job) -> dict | None:
        h = self.history(*job)
        if not h:
            return None
        top = max(r["attempt"] for r in h)
        return [r for r in h if r["attempt"] == top][-1]

    def new_attempt(self, run: str, dataset: str, receipt: str, variant: str, tier: str,
                    payload_sha256: str | None, reask: bool = False) -> dict:
        h = self.history(run, dataset, receipt, variant, tier)
        if reask and any(r.get("reask") for r in h):
            raise ValueError(f"{receipt}: a label re-ask was already made")
        attempt = 1 + max((r["attempt"] for r in h), default=0)
        return self.append(run=run, dataset=dataset, receipt=receipt, variant=variant, tier=tier, attempt=attempt,
                           status="planned", request_id=str(uuid.uuid4()), payload_sha256=payload_sha256,
                           reask=bool(reask), read_path=None)

    def mark(self, job: dict, status: str, **extra) -> dict:
        row = {k: job[k] for k in self.KEY}
        row.update({k: job.get(k) for k in ("request_id", "payload_sha256", "reask", "read_path")})
        row.update(status=status, **extra)
        return self.append(**row)

    def recover(self) -> int:
        """A job left `sent` without its stored answer (interrupted) becomes `failed`; returns how many."""
        last: dict = {}
        for r in self.rows():
            last[tuple(r[k] for k in self.KEY)] = r
        n = 0
        for r in last.values():
            if r["status"] == "sent" and not (r.get("read_path") and (ROOT / r["read_path"]).exists()):
                self.mark(r, "failed", reason="interrupted")
                n += 1
        return n

    def reusable(self, dataset: str, receipt: str, variant: str, tier: str, payload_sha256: str) -> dict | None:
        """A `done` job of any run with the same payload bytes (a revision reuses r0's labels and U reads)."""
        done = [r for r in self.rows() if r["status"] == "done" and (r["dataset"], r["receipt"], r["variant"], r["tier"])
                == (dataset, receipt, variant, tier) and r.get("payload_sha256") == payload_sha256]
        return done[-1] if done else None


# ---------------------------------------------------------------------------
# The guarded request
# ---------------------------------------------------------------------------
def sendable(job: dict, path: str | Path, chain) -> tuple[bytes, str]:
    if job.get("status") == "refused":
        raise NotSendable(f"{job['receipt']} {job['variant']}: refused by the Gate")
    if len(tuple(chain)) != 1:
        raise NotSendable("a masking-experiment request names exactly one model")
    data, mime = vlm.payload_bytes(path)
    if job.get("payload_sha256") and hashlib.sha256(data).hexdigest() != job["payload_sha256"]:
        raise NotSendable(f"{job['receipt']} {job['variant']}: payload changed since 25 mask; rerun 25 mask")
    return data, mime


class Budget:
    """One file for every dataset and run: {"format_version": 1, "campaigns": {name: {cap_base_usd,
    allowance_usd, reserved_usd, runs}}}. A request may go only if spent + reserved + its maximum fits."""

    def __init__(self, path: str | Path, campaign: str = CAMPAIGN, allowance_usd: float = ALLOWANCE_USD,
                 ledger=None):
        self.path = Path(path)
        self.campaign = campaign
        self.allowance = allowance_usd
        self.ledger = ledger or vlm.spend_total

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"format_version": 1, "campaigns": {}}

    def _save(self, d: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(_dump(d), encoding="utf-8")

    def open(self, run: str) -> dict:
        d = self._load()
        c = d["campaigns"].get(self.campaign)
        if c is None:          # written once; never reset within a campaign
            c = d["campaigns"][self.campaign] = {"cap_base_usd": round(self.ledger(), 6),
                                                 "allowance_usd": self.allowance, "reserved_usd": 0.0, "runs": []}
        if run not in c["runs"]:
            c["runs"].append(run)
        self._save(d)
        os.environ["HARNESS_SPEND_CAP_USD"] = f"{c['cap_base_usd'] + c['allowance_usd']:.6f}"
        return c

    def state(self) -> dict:
        return self._load()["campaigns"][self.campaign]

    def spent(self) -> float:
        return round(self.ledger() - self.state()["cap_base_usd"], 6)

    def reserve(self, amount: float) -> dict:
        d = self._load()
        c = d["campaigns"][self.campaign]
        before = self.ledger()
        if (before - c["cap_base_usd"]) + c["reserved_usd"] + amount > c["allowance_usd"] + 1e-12:
            raise BudgetExceeded(f"{self.campaign}: spent {before - c['cap_base_usd']:.4f} + reserved "
                                 f"{c['reserved_usd']:.4f} + {amount:.4f} > {c['allowance_usd']:.2f}")
        c["reserved_usd"] = round(c["reserved_usd"] + amount, 6)
        self._save(d)
        return {"amount": amount, "ledger_before": before}

    def settle(self, token: dict, sent: bool) -> bool:
        """Release the reservation when the request was not sent, or when the ledger shows its cost.
        A sent request with no recorded cost keeps it (counted as spent). Returns True when released."""
        d = self._load()
        c = d["campaigns"][self.campaign]
        release = (not sent) or self.ledger() > token["ledger_before"] + 1e-12
        if release:
            c["reserved_usd"] = round(max(0.0, c["reserved_usd"] - token["amount"]), 6)
            self._save(d)
        return release


def input_bound(results_root: str | Path, engine: str, prompt: str) -> int:
    """Largest input_tokens among the stored benchmark reads of that engine folder, plus the prompt's length
    in characters (a token never covers less than one character)."""
    best = 0
    for f in (Path(results_root) / engine).glob("*.json"):
        try:
            best = max(best, int(((json.loads(f.read_text(encoding="utf-8")).get("usage") or {}).get("input_tokens")) or 0))
        except (ValueError, OSError):
            continue
    if best == 0:
        raise ValueError(f"no stored reads with usage under {results_root}/{engine}")
    return best + len(prompt)


def send(table: JobTable, job: dict, path: str | Path, engine: str, budget: Budget, bound: int, store,
         prompt: str | None = None, schema: dict | None = None, validate=None, caller=None) -> dict | None:
    """One request for one planned job. store(record) -> repository-relative path of the saved read.
    Returns the record, or None when nothing usable came back (the job row says why)."""
    chain = vlm.ENGINE_CHAINS[engine]
    model = chain[0][1]
    try:
        sendable(job, path, chain)
        token = budget.reserve(vlm.max_request_usd(model, bound))
    except (NotSendable, BudgetExceeded) as exc:
        table.mark(job, "planned", reason=type(exc).__name__)
        raise
    table.mark(job, "sent")
    caller = caller or vlm.run_cloud_chain
    try:
        rec = caller(path, chain=chain, prompt=prompt, schema=schema, validate=validate, max_attempts=1)
    except vlm.SpendCapReached:
        budget.settle(token, sent=False)
        table.mark(job, "planned", reason="SpendCapReached")
        raise
    except Exception:
        budget.settle(token, sent=True)
        table.mark(job, "failed", reason="exception")
        raise
    budget.settle(token, sent=True)
    if rec.get("provider") == "none" or rec.get("engine") != model:
        table.mark(job, "failed", reason=f"provider {rec.get('provider')} engine {rec.get('engine')}")
        return None
    read_path = store(rec)
    table.mark(job, "done", read_path=read_path)
    return rec


# ---------------------------------------------------------------------------
# jobs.json (committed view) and replay arguments
# ---------------------------------------------------------------------------
def _tier_state(table: JobTable, paths: dict, key: str, variant: str, tier: str, read_file: Path) -> str:
    if read_file.exists():
        return "read"
    h = table.history(paths["run"], paths["dataset"], key, variant, tier)
    if not h:
        return "pending"
    last = table.latest(paths["run"], paths["dataset"], key, variant, tier)
    if last["status"] == "not_needed":
        return "not_needed"
    if all(r["status"] == "planned" and not r.get("reason") for r in h):
        return "pending"
    return "missing"


def jobs_view(paths: dict, variant: str, keys: list[str], table: JobTable, n_tags: dict, refused: set) -> dict:
    v = paths["variant"][variant]
    out = {}
    for k in sorted(keys):
        if variant != "U" and k in refused:
            out[k] = {"n_tags": 0, "t3": "refused", "t4": "refused"}
            continue
        t3 = _tier_state(table, paths, k, variant, "t3", v["reads_t3"] / f"{k}.json")
        if variant == "M2":
            t4 = "not_needed"
        elif t3 != "read":
            t4 = t3
        else:
            t4 = _tier_state(table, paths, k, variant, "t4", v["reads_t4"] / f"{k}.json")
        out[k] = {"n_tags": 0 if variant == "U" else int(n_tags.get(k, 0)), "t3": t3, "t4": t4}
    return {"format_version": 1, "run": paths["run"], "variant": variant, "receipts": out}


def write_jobs_view(paths: dict, variant: str, keys: list[str], table: JobTable, n_tags: dict, refused: set) -> Path:
    view = jobs_view(paths, variant, keys, table, n_tags, refused)
    p = paths["variant"][variant]["jobs_json"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_dump(view), encoding="utf-8")
    return p


def replay_args(paths: dict, variant: str) -> list[str]:
    """04_harness.py arguments for one variant; 04 runs from the repository root."""
    v = paths["variant"][variant]
    run = paths["run"]
    return ["--results", _rel(paths["results"]), "--manifest", _rel(paths["manifest"]),
            "--t3", f"pii/{run}/{variant}/gemini-lite", "--t4", f"pii/{run}/{variant}/gemini",
            "--keys", _rel(paths["sample"]), "--gates", "tags", "--jobs", _rel(v["jobs_json"]),
            "--out", _rel(v["harness"])]


# ---------------------------------------------------------------------------
# Metrics and verdict
# ---------------------------------------------------------------------------
def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _ok(rec: dict | None, gt: dict, day_first: bool) -> bool:
    if rec is None:
        return False
    return bool(money_fields_ok(correct_fields(predicted_fields(rec, day_first=day_first), gt)))


def inputs_sha256(files: list[Path]) -> dict:
    return {_rel(f): sha256_file(f) for f in sorted(files, key=lambda p: _rel(p)) if f.exists()}


def metrics_replay(paths: dict, keys: list[str], manifest: dict) -> dict:
    """Criteria 3 and 4 and the T3-alone accuracies, from committed files only."""
    views = {v: _load(paths["variant"][v]["jobs_json"]) for v in ("U", "M1", "M2")}
    acc = {}
    for v in ("U", "M1", "M2"):
        if not views[v]:
            continue
        read = [k for k in keys if views[v]["receipts"].get(k, {}).get("t3") == "read"]
        oks = [_ok(_load(paths["variant"][v]["reads_t3"] / f"{k}.json"), manifest[k]["gt"], manifest[k].get("day_first", True))
               for k in read]
        acc[v] = {"n": len(read), "correct": sum(oks), "share": round(sum(oks) / len(read), 4) if read else None}
    out: dict = {"t3_alone": acc}

    # Criterion 3: paired M1 - U on receipts read in both.
    if views["U"] and views["M1"]:
        pairs = [k for k in keys if views["U"]["receipts"].get(k, {}).get("t3") == "read"
                 and views["M1"]["receipts"].get(k, {}).get("t3") == "read"]
        left_out = sorted(set(keys) - set(pairs))
        if not pairs:
            out["criterion_3"] = {"status": "not decidable", "reason": "no pair", "left_out": left_out}
        else:
            m1 = [_ok(_load(paths["variant"]["M1"]["reads_t3"] / f"{k}.json"), manifest[k]["gt"], manifest[k].get("day_first", True)) for k in pairs]
            u = [_ok(_load(paths["variant"]["U"]["reads_t3"] / f"{k}.json"), manifest[k]["gt"], manifest[k].get("day_first", True)) for k in pairs]
            ci = paired_ci([int(x) for x in m1], [int(x) for x in u])
            lo, hi = ci["ci95"]
            out["criterion_3"] = {"status": "holds" if hi >= 0 else "fails", "improvement": lo > 0,
                                  "point": ci["point"], "ci95": ci["ci95"], "n_pairs": len(pairs), "left_out": left_out}

    # Criterion 4: review share of the M1 replay minus the U replay.
    reps = {v: _load(paths["variant"][v]["harness"] / "policies.json") for v in ("U", "M1")}
    if not (views["U"] and views["M1"] and reps["U"] and reps["M1"]):
        out["criterion_4"] = {"status": "not decidable", "reason": "replay missing"}
    else:
        bad = sorted(k for v in ("U", "M1") for k, j in views[v]["receipts"].items()
                     if j["t3"] in ("missing", "pending") or j["t4"] in ("missing", "pending"))
        row = {v: next(p for p in reps[v] if p["policy"] == "harness") for v in ("U", "M1")}
        diff = round((row["M1"]["review_share"] - row["U"]["review_share"]) * 100, 2)
        out["replay"] = {v: {"review_share": row[v]["review_share"], "accepted_money_precision": row[v]["accepted_money_precision"]}
                         for v in ("U", "M1")}
        if bad:
            out["criterion_4"] = {"status": "not decidable", "reason": "missing reads", "receipts": bad, "points": diff}
        else:
            out["criterion_4"] = {"status": "holds" if diff <= REVIEW_LIMIT_POINTS + 1e-9 else "fails", "points": diff}
    return out


def metrics_local(paths: dict, keys: list[str], manifest: dict) -> dict:
    """Gate cost, criteria 1 and 2, recall and over-masking; needs the local files."""
    views = {v: _load(paths["variant"][v]["jobs_json"]) for v in ("M1", "M2")}
    if not views["M1"]:
        raise FileNotFoundError("M1 jobs.json missing: run 25 mask first")
    out: dict = {"gate_cost": {v: round(sum(1 for k in keys if views[v] and views[v]["receipts"].get(k, {}).get("t3") == "refused") / len(keys), 4)
                               for v in ("M1", "M2")}}
    scope = [k for k in keys if views["M1"]["receipts"].get(k, {}).get("t3") != "refused"]
    checks = _load(paths["gt_checks"]) or {}
    invalid, not_hidden, L, H, items_n, items_hidden, by_rule = [], {}, 0, 0, 0, 0, {"ids": [0, 0], "coverage": [0, 0]}
    covered, unresolved, cannot, det_total, det_hidden = [], [], [], 0, 0
    for k in scope:
        rec = _load(paths["boxes"] / f"{k}.json")
        mm = _load(paths["mask_maps"] / f"{k}.M1.json")
        if rec is None or mm is None:
            raise FileNotFoundError(f"{k}: boxes or M1 mask map missing")
        det_total += len(rec["tokens"])
        det_hidden += len(mm["hide"])
        lab_path = paths["labels"] / f"{k}.json"
        try:
            lab = mask.load_labels(lab_path, rec["tokens"]) if lab_path.exists() else None
        except ValueError:
            lab = None
        if lab is None or lab.get("status") != "valid":
            invalid.append(k)
        else:
            hidden_set = set(mm["hide"])
            for it in lab["items"]:
                ok, how = mask.item_hidden(it, mm)
                items_n += 1
                items_hidden += ok
                by_rule[how][0] += ok
                by_rule[how][1] += 1
                if not ok:
                    not_hidden.setdefault(k, []).append(it["category"])
                for i in it.get("detection_ids") or []:
                    L += 1
                    H += i in hidden_set
        # Criterion 2: ground truth under the fill.
        loc = mask.locate_gt(rec["tokens"], manifest[k]["gt"])
        by_id = {d["id"]: d for d in rec["tokens"]}
        hit = any(mask.fill_overlaps(by_id[i], mm) for f in ("date", "total") for i in (loc[f] or []))
        if hit:
            covered.append(k)
            continue
        if any(loc[f] == [] for f in ("date", "total")):
            c = checks.get(k)
            if not c or c.get("fill_sha256") != mm["fill_sha256"]:
                unresolved.append(k)
            elif c["result"] == "covered":
                covered.append(k)
            elif c["result"] == "cannot tell":
                cannot.append(k)
    c1 = ({"status": "not decidable", "reason": "invalid labels", "receipts": sorted(invalid)} if invalid else
          {"status": "holds" if not not_hidden else "fails", "receipts": sorted(not_hidden),
           "categories": sorted({c for cs in not_hidden.values() for c in cs})})
    c2 = ({"status": "fails", "receipts": sorted(covered)} if covered else
          {"status": "not decidable", "receipts": sorted(unresolved + cannot)} if unresolved or cannot else
          {"status": "holds"})
    out.update(criterion_1=c1, criterion_2=c2, scope=len(scope),
               detection_recall=round(H / L, 4) if L else None, end_to_end_recall=round(items_hidden / items_n, 4) if items_n else None,
               labeled_items=items_n, recall_by_rule={k: (round(a / b, 4) if b else None) for k, (a, b) in by_rule.items()},
               hidden_detection_share=round(det_hidden / det_total, 4) if det_total else None)
    return out


def verdict(replay: dict, local: dict) -> str:
    status = {1: local["criterion_1"]["status"], 2: local["criterion_2"]["status"],
              3: replay.get("criterion_3", {}).get("status", "not decidable"),
              4: replay.get("criterion_4", {}).get("status", "not decidable")}
    fails = [k for k, s in status.items() if s == "fails"]
    if fails:
        return "fails criterion " + ", ".join(map(str, fails))
    nd = [k for k, s in status.items() if s != "holds"]
    if nd:
        return "not decidable (criterion " + ", ".join(map(str, nd)) + ")"
    return "works on this sample"


def write_pii_json(paths: dict, run: str, part: str, data: dict) -> Path:
    """The only writer of results*/harness/pii.json: replaces one part of one run, sorted keys, no time stamps."""
    if part not in ("replay", "local"):
        raise ValueError(part)
    p = paths["pii_json"]
    doc = _load(p) or {"schema_version": 1, "runs": {}}
    doc["runs"].setdefault(run, {})[part] = data
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_dump(doc), encoding="utf-8")
    return p
