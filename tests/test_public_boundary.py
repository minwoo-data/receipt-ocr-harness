"""Public/local boundary: .githooks/private-paths is the one list of paths that never leave this machine.

Checks that .gitignore covers each line, that no tracked file matches one, that docs/ (the public
Pages folder) holds no ignored file outside the listed paths, and that the pre-commit hook refuses
a listed path even after `git add -f`.
"""
import fnmatch
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT / ".githooks" / "private-paths"

pytestmark = pytest.mark.skipif(shutil.which("git") is None or not (ROOT / ".git").exists(), reason="needs a git checkout")


def patterns() -> list[str]:
    out = []
    for line in LIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def matches(path: str, pat: str) -> bool:
    return path.startswith(pat) if pat.endswith("/") else fnmatch.fnmatchcase(path, pat)


def git(*args: str, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check)


def probe(pat: str) -> str:
    """A path that the pattern covers, for git check-ignore."""
    if pat.endswith("/"):
        return pat + "probe.txt"
    return pat.replace("*", "probe")


def test_every_private_path_is_gitignored():
    missing = [p for p in patterns() if git("check-ignore", "-q", "--no-index", probe(p), check=False).returncode != 0]
    assert not missing, f".gitignore does not cover: {missing}"


def test_no_private_path_is_tracked():
    tracked = git("ls-files").stdout.splitlines()
    bad = [f for f in tracked for p in patterns() if matches(f, p)]
    assert not bad, f"tracked but listed as local-only: {bad}"


def test_docs_holds_no_unlisted_ignored_file():
    # docs/ is published by Pages; a git-ignored file there is a private file one `git add -f` away from it
    ignored = git("ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "docs").stdout.splitlines()
    bad = [f for f in ignored if not any(matches(f, p) or matches(f.rstrip("/") + "/", p) for p in patterns())]
    assert not bad, f"ignored files in docs/ that are not in private-paths (move them to notes/): {bad}"


def test_masking_local_root_is_listed():
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from harness.mask import LOCAL_ROOT
    rel = LOCAL_ROOT.relative_to(ROOT).as_posix() + "/sroie300/jobs.jsonl"
    assert any(matches(rel, p) for p in patterns()), f"{rel} is not covered by .githooks/private-paths"
    assert any(matches("results/pii_local/x.json", p) for p in patterns()), "a pii_local folder anywhere is private"


def test_hook_refuses_private_paths_even_when_forced(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".githooks").mkdir(parents=True)
    shutil.copy(ROOT / ".githooks" / "pre-commit", repo / ".githooks" / "pre-commit")
    shutil.copy(LIST, repo / ".githooks" / "private-paths")
    git("init", "-q", cwd=repo)
    git("config", "core.hooksPath", ".githooks", cwd=repo)
    git("config", "user.name", "test", cwd=repo)
    git("config", "user.email", "test@example.invalid", cwd=repo)
    (repo / "README.md").write_text("public\n", encoding="utf-8")
    git("add", ".githooks", "README.md", cwd=repo)
    assert git("commit", "-q", "-m", "public", cwd=repo, check=False).returncode == 0

    for rel in ("notes/booth.html", "docs/discussion/x/round-1.md", "docs/CONTEXT.md", "CLAUDE.md",
                "data/raw/pii_local/sroie300/jobs.jsonl", "docs/companion_preview.png"):
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("private\n", encoding="utf-8")
        git("add", "-f", rel, cwd=repo)
        r = git("commit", "-q", "-m", "private", cwd=repo, check=False)
        assert r.returncode != 0, f"hook let {rel} through"
        assert "local-only" in r.stderr, r.stderr
        git("reset", "-q", cwd=repo)

    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "index.html").write_text("<p>public</p>\n", encoding="utf-8")
    git("add", "docs/index.html", cwd=repo)
    assert git("commit", "-q", "-m", "page", cwd=repo, check=False).returncode == 0
