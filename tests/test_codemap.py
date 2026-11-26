"""The code map is generated from code, so it can never drift from it."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "template" / "tools"
spec = importlib.util.spec_from_file_location("codemap", TOOLS / "codemap.py")
codemap = importlib.util.module_from_spec(spec)
sys.modules["codemap"] = codemap
spec.loader.exec_module(codemap)


def write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_symbols_are_extracted_per_language(tmp_path):
    write(tmp_path, "src/app/service.py", "import os\n\nclass Service:\n    def run(self): ...\n\ndef helper():\n    pass\n_private = 1\n")
    write(tmp_path, "app/src/main/kotlin/Login.kt", "package x\n\ndata class User(val id: String)\nfun login() {}\n  fun nested() {}\nobject Repo\n")
    write(tmp_path, "crates/core/src/lib.rs", "pub fn parse() {}\nfn private() {}\npub struct Token;\npub(crate) enum Kind {}\n")
    write(tmp_path, "ios/Views.swift", "struct LoginView: View {}\nfunc helper() {}\n")
    entries = codemap.scan(tmp_path, ("src", "app/src/main", "crates", "ios"))
    as_dict = {entry.path: entry.symbols for entry in entries}
    assert as_dict["src/app/service.py"] == ("class Service", "def helper")
    assert as_dict["app/src/main/kotlin/Login.kt"] == ("class User", "fun login", "object Repo")
    assert as_dict["crates/core/src/lib.rs"] == ("fn parse", "struct Token", "enum Kind")
    assert as_dict["ios/Views.swift"] == ("struct LoginView", "func helper")


def test_output_is_deterministic_and_sorted(tmp_path):
    write(tmp_path, "src/b.py", "def b(): ...\n")
    write(tmp_path, "src/a.py", "def a(): ...\n")
    first = codemap.render(codemap.scan(tmp_path, ("src",)))
    second = codemap.render(codemap.scan(tmp_path, ("src",)))
    assert first == second
    assert first.index("src/a.py") < first.index("src/b.py")


def test_missing_roots_are_skipped(tmp_path):
    assert codemap.scan(tmp_path, ("does-not-exist",)) == []


def test_check_mode_fails_when_the_map_is_stale(tmp_path, monkeypatch):
    write(tmp_path, "src/a.py", "def a(): ...\n")
    monkeypatch.chdir(tmp_path)
    assert codemap.main(["--roots", "src", "--output", "docs/CODEMAP.md"]) == 0
    assert codemap.main(["--roots", "src", "--output", "docs/CODEMAP.md", "--check"]) == 0
    write(tmp_path, "src/a.py", "def a(): ...\ndef b(): ...\n")
    assert codemap.main(["--roots", "src", "--output", "docs/CODEMAP.md", "--check"]) == 1
