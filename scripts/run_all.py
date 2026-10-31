"""run_all.py - the analysis chain, in order, for both datasets, then the poster.
    python scripts/run_all.py
"""
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
steps = [
    [PY, "scripts/04_harness.py", "--results", "results"],
    [PY, "scripts/04_harness.py", "--manifest", "data/manifest/wild200.jsonl", "--results", "results_wild"],
    [PY, "scripts/12_leaks.py", "--results", "results"],
    [PY, "scripts/12_leaks.py", "--results", "results_wild"],
    [PY, "scripts/14_learned_router.py", "--results", "results"],
    [PY, "scripts/14_learned_router.py", "--results", "results_wild", "--fit-from", "results"],
    [PY, "scripts/06_charts.py"],
    [PY, "scripts/10_fill_poster.py"],
    [PY, "scripts/09_render_poster.py"],
]
for cmd in steps:
    print(">>", " ".join(cmd[1:]))
    subprocess.run(cmd, cwd=ROOT, check=True)
print("run_all: done")
