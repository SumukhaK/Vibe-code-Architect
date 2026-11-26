"""A bug fix must come with a test that fails on the old code and passes on the new."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "template" / "tools"
_SOURCE = str(TOOLS / "{% if 'python' in stacks %}red_green.py{% endif %}")
spec = importlib.util.spec_from_loader(
    "red_green", importlib.machinery.SourceFileLoader("red_green", _SOURCE)
)
red_green = importlib.util.module_from_spec(spec)
sys.modules["red_green"] = red_green
spec.loader.exec_module(red_green)


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "src" / "calc").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "calc" / "__init__.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )
    (root / "tests" / "test_existing.py").write_text(
        "def test_nothing():\n    assert True\n", encoding="utf-8"
    )
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "base with bug")
    git(root, "checkout", "-q", "-b", "bugfix/add")
    return root


def commit(root: Path, message: str) -> None:
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", message)


def test_real_fix_with_a_failing_then_passing_test_is_proven(repo, monkeypatch):
    (repo / "src" / "calc" / "__init__.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    (repo / "tests" / "test_add.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8"
    )
    commit(repo, "fix add")
    monkeypatch.chdir(repo)
    assert red_green.main(["--base", "main"]) == 0


def test_a_test_that_already_passes_on_the_old_code_is_not_proof(repo, monkeypatch):
    (repo / "src" / "calc" / "__init__.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    (repo / "tests" / "test_add.py").write_text(
        "from calc import add\n\ndef test_add_zero():\n    assert add(0, 0) == 0\n",
        encoding="utf-8",
    )
    commit(repo, "fix add, weak test")
    monkeypatch.chdir(repo)
    assert red_green.main(["--base", "main"]) == 1


def test_a_bug_fix_without_a_new_test_fails(repo, monkeypatch):
    (repo / "src" / "calc" / "__init__.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    commit(repo, "fix add, no test")
    monkeypatch.chdir(repo)
    assert red_green.main(["--base", "main"]) == 1


def test_the_temporary_worktree_is_removed(repo, monkeypatch):
    (repo / "tests" / "test_add.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8"
    )
    commit(repo, "test only")
    monkeypatch.chdir(repo)
    red_green.main(["--base", "main"])
    listing = subprocess.run(
        ["git", "worktree", "list"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout
    assert len(listing.strip().splitlines()) == 1
