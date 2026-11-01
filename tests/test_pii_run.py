"""Running and judging the masking experiment (docs/plan-pii-mask.md): job table, the guarded request with a
fake caller (no network), the budget reservation, the jobs.json view, replay arguments, the verdict, and the
04 routing of refused receipts. Everything runs in tmp_path; nothing touches the real ledger or local root."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from harness import mask, pii_run  # noqa: E402
from harness.engines import vlm  # noqa: E402


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), ROOT / "scripts" / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def img(tmp_path):
    from PIL import Image
    p = tmp_path / "m.png"
    Image.new("RGB", (40, 20), (255, 255, 255)).save(p)
    return p


@pytest.fixture
def table(tmp_path):
    return pii_run.JobTable(tmp_path / "jobs.jsonl")


class Ledger:
    def __init__(self):
        self.total = 1.0

    def __call__(self):
        return self.total


def job_for(table, img, status=None):
    import hashlib
    data, _ = vlm.payload_bytes(img)
    j = table.new_attempt("r0", "sroie300", "K1", "M1", "t3", hashlib.sha256(data).hexdigest())
    if status:
        j = table.mark(j, status)
    return j


def record(model, provider="gemini"):
    return {"engine": model, "provider": provider, "data": {"date": "2018-03-25", "total": 26.5}, "usage": {}}


# ---- job table -------------------------------------------------------------------------------------------
def test_job_table_attempts_reask_and_recover(table, img):
    j = job_for(table, img)
    assert j["attempt"] == 1 and j["status"] == "planned" and len(j["request_id"]) == 36
    table.mark(j, "sent")
    assert table.recover() == 1 and table.latest("r0", "sroie300", "K1", "M1", "t3")["status"] == "failed"
    assert table.new_attempt("r0", "sroie300", "K1", "M1", "t3", "x")["attempt"] == 2
    table.new_attempt("r0", "sroie300", "K1", "U", "label", "x", reask=True)
    with pytest.raises(ValueError):
        table.new_attempt("r0", "sroie300", "K1", "U", "label", "x", reask=True)


# ---- the guarded request ---------------------------------------------------------------------------------
def test_refused_receipt_causes_no_call_at_any_tier(tmp_path, table, img):
    budget = pii_run.Budget(tmp_path / "budget.json", ledger=Ledger())
    budget.open("r0")
    calls = []
    for tier in ("t3", "t4"):
        j = table.new_attempt("r0", "sroie300", "K9", "M1", tier, None)
        j = table.mark(j, "refused")
        with pytest.raises(pii_run.NotSendable):
            pii_run.send(table, j, img, "gemini-lite", budget, 1000, store=lambda r: "x",
                         caller=lambda *a, **k: calls.append(1))
    assert calls == [] and budget.state()["reserved_usd"] == 0.0


def test_changed_payload_stays_planned(tmp_path, table, img):
    budget = pii_run.Budget(tmp_path / "budget.json", ledger=Ledger())
    budget.open("r0")
    j = job_for(table, img)
    from PIL import Image
    Image.new("RGB", (40, 20), (0, 0, 0)).save(img)            # the masked file changed after 25 mask
    with pytest.raises(pii_run.NotSendable):
        pii_run.send(table, j, img, "gemini-lite", budget, 1000, store=lambda r: "x", caller=lambda *a, **k: 1 / 0)
    last = table.latest("r0", "sroie300", "K1", "M1", "t3")
    assert last["status"] == "planned" and last["reason"] == "NotSendable"


def test_send_success_failure_and_cap(tmp_path, table, img):
    led = Ledger()
    budget = pii_run.Budget(tmp_path / "budget.json", ledger=led)
    budget.open("r0")
    model = vlm.ENGINE_CHAINS["gemini-lite"][0][1]
    seen = {}

    def ok_caller(path, **kw):
        seen.update(kw)
        led.total += 0.0004                                   # the ledger records the request's cost
        return record(model)

    rec = pii_run.send(table, job_for(table, img), img, "gemini-lite", budget, 1000, store=lambda r: "reads/K1.json",
                       caller=ok_caller)
    assert rec and seen["max_attempts"] == 1 and seen["chain"] == vlm.ENGINE_CHAINS["gemini-lite"]
    assert table.latest("r0", "sroie300", "K1", "M1", "t3")["status"] == "done"
    assert budget.state()["reserved_usd"] == 0.0             # released: the ledger shows the cost

    # an answer from another model, or provider none, is never stored
    stored = []
    assert pii_run.send(table, table.new_attempt("r0", "sroie300", "K1", "M1", "t3", None), img, "gemini-lite", budget,
                        1000, store=stored.append, caller=lambda p, **kw: record("claude-haiku-5-5", "claude")) is None
    assert stored == [] and table.latest("r0", "sroie300", "K1", "M1", "t3")["status"] == "failed"
    assert budget.state()["reserved_usd"] > 0                # sent but no recorded cost: kept as spent

    def cap(path, **kw):
        raise vlm.SpendCapReached("cap")
    before = budget.state()["reserved_usd"]
    with pytest.raises(vlm.SpendCapReached):
        pii_run.send(table, table.new_attempt("r0", "sroie300", "K1", "M1", "t3", None), img, "gemini-lite", budget,
                     1000, store=stored.append, caller=cap)
    assert budget.state()["reserved_usd"] == before and table.latest("r0", "sroie300", "K1", "M1", "t3")["status"] == "planned"


def test_budget_reservation_bounds_the_allowance(tmp_path):
    led = Ledger()
    b = pii_run.Budget(tmp_path / "budget.json", allowance_usd=0.01, ledger=led)
    c = b.open("r0")
    assert c["cap_base_usd"] == 1.0
    t = b.reserve(0.006)
    with pytest.raises(pii_run.BudgetExceeded):
        b.reserve(0.006)
    assert b.settle(t, sent=True) is False                    # no cost recorded: still reserved
    led.total += 0.001
    t2 = b.reserve(0.002)
    led.total += 0.002
    assert b.settle(t2, sent=True) is True
    b2 = pii_run.Budget(tmp_path / "budget.json", allowance_usd=0.01, ledger=lambda: 5.0)
    assert b2.open("rev1")["cap_base_usd"] == 1.0              # never reset within a campaign
    assert b2.state()["runs"] == ["r0", "rev1"]


def test_max_request_usd_and_engine_chains_match_02():
    model = vlm.GEMINI_LITE_MODEL
    assert vlm.max_request_usd(model, 1000) == pytest.approx((1000 * 0.25 + vlm.MAX_OUTPUT_TOKENS * 1.50) / 1e6)
    with pytest.raises(ValueError):
        vlm.max_request_usd("no-such-model", 10)
    e02 = load_script("02_run_engine.py").VLM_ENGINES
    for name, chain in vlm.ENGINE_CHAINS.items():
        assert tuple(tuple(x) for x in e02[name]["chain"]) == chain, name
        assert len(chain) == 1


# ---- jobs.json view and replay arguments ------------------------------------------------------------------
def test_jobs_view_states(tmp_path, table):
    P = mask.pii_paths(tmp_path / "results", "data/manifest/sroie300.jsonl")
    keys = ["A", "B", "C", "D", "E"]
    for k in ("A", "B"):                       # A: read; B: read at T3, not flagged for T4
        p = P["variant"]["M1"]["reads_t3"] / f"{k}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}", encoding="utf-8")
    t4 = P["variant"]["M1"]["reads_t4"] / "A.json"
    t4.parent.mkdir(parents=True, exist_ok=True)
    t4.write_text("{}", encoding="utf-8")
    jb = table.new_attempt("r0", "sroie300", "B", "M1", "t4", None)
    table.mark(jb, "not_needed")
    jd = table.new_attempt("r0", "sroie300", "D", "M1", "t3", None)
    table.mark(jd, "failed", reason="provider")
    v = pii_run.jobs_view(P, "M1", keys, table, {"A": 2, "B": 1}, refused={"C"})
    r = v["receipts"]
    assert v["format_version"] == 1 and v["run"] == "r0"
    assert r["A"] == {"n_tags": 2, "t3": "read", "t4": "read"}
    assert r["B"]["t4"] == "not_needed" and r["C"]["t3"] == "refused"
    assert r["D"]["t3"] == "missing" and r["E"]["t3"] == "pending"
    m2 = pii_run.jobs_view(P, "M2", keys, table, {}, refused=set())
    assert all(x["t4"] == "not_needed" for x in m2["receipts"].values())
    u = pii_run.jobs_view(P, "U", keys, table, {"A": 2}, refused={"C"})
    assert u["receipts"]["C"]["t3"] != "refused" and u["receipts"]["A"]["n_tags"] == 0
    text = (pii_run.write_jobs_view(P, "M1", keys, table, {}, set())).read_text(encoding="utf-8")
    assert "request_id" not in text and not __import__("re").search(r"[0-9a-f]{8}-[0-9a-f]{4}-4", text)


def test_replay_args_are_repository_relative():
    P = mask.pii_paths(ROOT / "results_wild", ROOT / "data" / "manifest" / "wild200.jsonl")
    a = pii_run.replay_args(P, "M1")
    d = dict(zip(a[::2], a[1::2]))
    assert d["--results"] == "results_wild" and d["--manifest"] == "data/manifest/wild200.jsonl"
    assert d["--t3"] == "pii/r0/M1/gemini-lite" and d["--jobs"] == "results_wild/pii/r0/M1/jobs.json"
    assert d["--out"] == "results_wild/pii/r0/M1/harness" and d["--gates"] == "tags"


# ---- metrics and verdict ----------------------------------------------------------------------------------
def test_metrics_replay_criteria_3_and_4(tmp_path):
    P = mask.pii_paths(tmp_path / "results", "data/manifest/sroie300.jsonl")
    keys = [f"K{i}" for i in range(6)]
    manifest = {k: {"gt": {"date": "2018-03-25", "total": 26.5}} for k in keys}
    for v in ("U", "M1"):
        vv = P["variant"][v]
        vv["reads_t3"].mkdir(parents=True)
        vv["harness"].mkdir(parents=True)
        for k in keys:
            (vv["reads_t3"] / f"{k}.json").write_text(json.dumps(record("m")), encoding="utf-8")
        view = {"format_version": 1, "run": "r0", "variant": v,
                "receipts": {k: {"n_tags": 0, "t3": "read", "t4": "not_needed"} for k in keys}}
        vv["jobs_json"].write_text(json.dumps(view), encoding="utf-8")
        (vv["harness"] / "policies.json").write_text(json.dumps(
            [{"policy": "harness", "review_share": 0.1 if v == "U" else 0.2667, "accepted_money_precision": 1.0}]), encoding="utf-8")
    out = pii_run.metrics_replay(P, keys, manifest)
    assert out["criterion_3"]["status"] == "holds" and out["criterion_3"]["n_pairs"] == 6
    assert out["criterion_4"]["status"] == "fails" and out["criterion_4"]["points"] == pytest.approx(16.67)
    view = json.loads(P["variant"]["M1"]["jobs_json"].read_text(encoding="utf-8"))
    view["receipts"]["K0"]["t4"] = "missing"
    P["variant"]["M1"]["jobs_json"].write_text(json.dumps(view), encoding="utf-8")
    assert pii_run.metrics_replay(P, keys, manifest)["criterion_4"]["status"] == "not decidable"


def test_verdict():
    rep = {"criterion_3": {"status": "holds"}, "criterion_4": {"status": "holds"}}
    loc = {"criterion_1": {"status": "holds"}, "criterion_2": {"status": "holds"}}
    assert pii_run.verdict(rep, loc) == "works on this sample"
    assert pii_run.verdict(rep, {**loc, "criterion_1": {"status": "fails"}}) == "fails criterion 1"
    assert pii_run.verdict({**rep, "criterion_4": {"status": "not decidable"}}, loc) == "not decidable (criterion 4)"


def test_write_pii_json_keeps_parts_and_runs(tmp_path):
    P = mask.pii_paths(tmp_path / "results", "data/manifest/sroie300.jsonl")
    pii_run.write_pii_json(P, "r0", "replay", {"b": 1, "a": 2})
    pii_run.write_pii_json(P, "r0", "local", {"x": 1})
    pii_run.write_pii_json(P, "rev1", "replay", {"y": 1})
    first = P["pii_json"].read_text(encoding="utf-8")
    d = json.loads(first)
    assert d["schema_version"] == 1 and set(d["runs"]) == {"r0", "rev1"} and set(d["runs"]["r0"]) == {"replay", "local"}
    assert first.index('"a"') < first.index('"b"')            # sorted keys
    pii_run.write_pii_json(P, "rev1", "replay", {"y": 1})
    assert P["pii_json"].read_text(encoding="utf-8") == first  # unchanged rerun is byte-identical


# ---- 04: a refused receipt is review right after T1 -------------------------------------------------------
def test_04_refused_receipt_goes_to_review_after_t1():
    h = load_script("04_harness.py")
    ev = lambda ok: {"pred": {}, "correct": {}, "money_ok": ok, "all_ok": ok, "cost": 0.001, "latency_ms": 10, "available": True}  # noqa: E731
    row = {"key": "K", "t1": ev(False), "t1b": ev(False), "t2": ev(False), "t3": ev(True), "t4": ev(True),
           "signal": {"agree": False, "conf": 0.5, "complete": False, "date_ok": True},
           "flags": {"t2": [], "t3": [], "t4": []}}
    assert h.decide(row, "harness", {"tau": 0.9})["tier"] == "T3"
    d = h.decide({**row, "refused": True}, "harness", {"tau": 0.9})
    assert d == {"tier": "review", "path": ["T1"], "cost": 0.001, "latency_ms": 10}
    assert h.summarize([{**row, "refused": True}], "harness", {"tau": 0.9})["cloud_sent_share"] == 0.0
