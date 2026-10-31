"""run_all.py - the offline analysis chain, in order, for both datasets, then every page. No API calls.
    python scripts/run_all.py            # analysis + README blocks + landing page + local demo
    python scripts/run_all.py --poster   # also re-render poster.html and the PDF (not after submission)

The poster PDF was submitted on 2026-10-31, so by default the chain does not touch it and checks at
the end that its bytes still match poster/printed_numbers.json.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
SROIE = ["--results", "results"]
WILD = ["--manifest", "data/manifest/wild200.jsonl", "--results", "results_wild"]
steps = [
    # engines named explicitly: 03_score would otherwise treat analysis folders (hedge/, leaks/, ...) as engines
    [PY, "scripts/03_score.py", *SROIE, "--engines", "rapidocr", "tesseract", "qwen", "gemini-lite", "gemini"],
    [PY, "scripts/03_score.py", *WILD, "--engines", "gemini", "gemini-lite", "qwen", "rapidocr", "tesseract"],
    [PY, "scripts/04_harness.py", *SROIE],
    [PY, "scripts/04_harness.py", *WILD],
    # D: the frozen total-label gate (opt-in), dev and held-out
    [PY, "scripts/04_harness.py", *SROIE, "--gates", "total_label", "--out", "results/gate_total_label/harness"],
    [PY, "scripts/17_gate_experiment.py", "--results", "results", "--role", "dev (gate designed here)"],
    [PY, "scripts/04_harness.py", *WILD, "--gates", "total_label", "--out", "results_wild/gate_total_label/harness"],
    [PY, "scripts/17_gate_experiment.py", "--results", "results_wild", "--role", "held-out (gate frozen at 07a5a7a)"],
    [PY, "scripts/12_leaks.py", "--results", "results"],
    [PY, "scripts/12_leaks.py", "--results", "results_wild"],
    [PY, "scripts/14_learned_router.py", "--results", "results"],
    [PY, "scripts/14_learned_router.py", "--results", "results_wild", "--fit-from", "results"],
    [PY, "scripts/19_backstop.py", *SROIE],
    [PY, "scripts/19_backstop.py", *WILD],
    [PY, "scripts/20_bootstrap.py", "--results", "results"],
    [PY, "scripts/20_bootstrap.py", "--results", "results_wild"],
    [PY, "scripts/06_charts.py"],
    [PY, "scripts/15_companion.py"],
    [PY, "scripts/16_workflow_pages.py"],
    [PY, "scripts/22_readme.py"],
    [PY, "scripts/18_landing.py"],      # copies the submitted PDF into docs/assets
    [PY, "scripts/21_demo.py"],         # demo/index.html, git-ignored
]
if "--poster" in sys.argv:
    steps[-3:-3] = [[PY, "scripts/10_fill_poster.py"], [PY, "scripts/09_render_poster.py"]]
for cmd in steps:
    print(">>", " ".join(cmd[1:]), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)
if "--poster" not in sys.argv:
    frozen = json.loads((ROOT / "poster" / "printed_numbers.json").read_text(encoding="utf-8"))
    pdf = ROOT / "poster" / frozen["pdf"]
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == frozen["pdf_sha256"], "the submitted poster PDF changed"
    print("poster PDF unchanged (sha256 matches poster/printed_numbers.json)")
print("run_all: done")
