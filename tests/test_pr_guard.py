"""Behaviour of the PR guard that every generated project runs in CI."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "template" / "tools"
spec = importlib.util.spec_from_file_location("pr_guard", TOOLS / "pr_guard.py")
pr_guard = importlib.util.module_from_spec(spec)
sys.modules["pr_guard"] = pr_guard
spec.loader.exec_module(pr_guard)

CONFIG = pr_guard.Config(
    branch_pattern=r"^(feature|bugfix|upkeep)/[a-z0-9][a-z0-9-]*$",
    max_changed_lines=300,
    max_changed_files=12,
    size_ignore_globs=("**/*.lock", "docs/**"),
    source_globs=("src/**",),
    test_globs=("tests/**",),
    protected_globs=(".github/**", "guardrails.toml"),
    guardrail_branch_prefix="upkeep/",
)

GOOD_BODY = """## Linked issue
Closes #12

## Verification
<!-- How do you know it works? -->
`pytest tests/test_login.py` — 4 passed, the new test failed before the fix.
"""


@pytest.mark.parametrize(
    "path, pattern, expected",
    [
        ("src/app/main.py", "src/**", True),
        ("src/main.py", "src/**", True),
        ("tests/test_x.py", "src/**", False),
        ("app/src/test/Foo.kt", "**/src/test/**", True),
        ("src/test/Foo.kt", "**/src/test/**", True),
        ("poetry.lock", "**/*.lock", True),
        ("a/b/poetry.lock", "**/*.lock", True),
        ("srcx/main.py", "src/**", False),
        ("guardrails.toml", "guardrails.toml", True),
    ],
)
def test_glob_matching(path, pattern, expected):
    assert pr_guard.matches(path, (pattern,)) is expected


@pytest.mark.parametrize(
    "branch, ok",
    [
        ("feature/login-screen", True),
        ("bugfix/null-crash", True),
        ("upkeep/bump-ruff", True),
        ("main", False),
        ("feature/Login Screen", False),
        ("fix/thing", False),
    ],
)
def test_branch_names_follow_the_convention(branch, ok):
    assert (pr_guard.check_branch(branch, CONFIG) == []) is ok


def test_small_pr_passes_and_ignored_files_do_not_count():
    changes = [
        pr_guard.Change("src/a.py", 120, 30),
        pr_guard.Change("uv.lock", 5000, 4000),
        pr_guard.Change("docs/notes.md", 900, 0),
    ]
    assert pr_guard.check_size(changes, CONFIG) == []


def test_too_many_lines_fails_with_the_numbers():
    problems = pr_guard.check_size([pr_guard.Change("src/a.py", 250, 51)], CONFIG)
    assert problems and "301" in problems[0] and "300" in problems[0]


def test_too_many_files_fails():
    changes = [pr_guard.Change(f"src/m{i}.py", 1, 0) for i in range(13)]
    assert any("13 files" in p for p in pr_guard.check_size(changes, CONFIG))


def test_source_change_without_test_change_fails():
    assert pr_guard.check_tests(["src/a.py"], GOOD_BODY, CONFIG)


def test_source_change_with_test_change_passes():
    assert pr_guard.check_tests(["src/a.py", "tests/test_a.py"], GOOD_BODY, CONFIG) == []


def test_docs_only_change_needs_no_tests():
    assert pr_guard.check_tests(["docs/PRD.md"], GOOD_BODY, CONFIG) == []


def test_explicit_no_test_reason_is_accepted_and_visible_to_the_reviewer():
    body = GOOD_BODY + "\nNo tests: pure rename, behaviour unchanged.\n"
    assert pr_guard.check_tests(["src/a.py"], body, CONFIG) == []


def test_empty_no_test_reason_is_not_accepted():
    body = GOOD_BODY + "\nNo tests:\n"
    assert pr_guard.check_tests(["src/a.py"], body, CONFIG)


@pytest.mark.parametrize("keyword", ["Closes", "fixes", "Resolves"])
def test_issue_link_is_required(keyword):
    assert pr_guard.check_issue_link(f"{keyword} #7") == []
    assert pr_guard.check_issue_link("Related to the login work") != []


def test_verification_section_must_have_real_content():
    assert pr_guard.check_verification(GOOD_BODY) == []
    empty = "## Linked issue\nCloses #1\n\n## Verification\n<!-- How do you know it works? -->\n\n## Notes\nx"
    assert pr_guard.check_verification(empty)
    assert pr_guard.check_verification("Closes #1")


def test_feature_branch_cannot_touch_guardrails():
    problems = pr_guard.check_protected(
        ["src/a.py", ".github/workflows/ci.yml"], "feature/login", CONFIG
    )
    assert problems and ".github/workflows/ci.yml" in problems[0]


def test_upkeep_branch_may_change_guardrails():
    assert pr_guard.check_protected(["guardrails.toml"], "upkeep/raise-limit", CONFIG) == []


def test_numstat_parsing_handles_binary_and_renames():
    text = "10\t2\tsrc/a.py\n-\t-\tassets/logo.png\n3\t1\tsrc/{old => new}.py\n"
    changes = pr_guard.parse_numstat(text)
    assert changes == [
        pr_guard.Change("src/a.py", 10, 2),
        pr_guard.Change("assets/logo.png", 0, 0),
        pr_guard.Change("src/new.py", 3, 1),
    ]


def test_config_is_read_from_guardrails_toml(tmp_path):
    (tmp_path / "guardrails.toml").write_text(
        '[pr]\nbranch_pattern = "^x/"\nmax_changed_lines = 10\nmax_changed_files = 2\n'
        'size_ignore_globs = []\nprotected_globs = []\nguardrail_branch_prefix = "upkeep/"\n'
        '[tests]\nsource_globs = ["src/**"]\ntest_globs = ["tests/**"]\n',
        encoding="utf-8",
    )
    config = pr_guard.load_config(tmp_path / "guardrails.toml")
    assert config.max_changed_lines == 10 and config.source_globs == ("src/**",)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_end_to_end_against_a_real_git_history(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "guardrails.toml").write_text(
        '[pr]\nbranch_pattern = "^(feature|bugfix|upkeep)/"\nmax_changed_lines = 300\n'
        "max_changed_files = 12\nsize_ignore_globs = []\n"
        'protected_globs = ["guardrails.toml"]\nguardrail_branch_prefix = "upkeep/"\n'
        '[tests]\nsource_globs = ["src/**"]\ntest_globs = ["tests/**"]\n',
        encoding="utf-8",
    )
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "feature/add-y")
    (repo / "src" / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "add y")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("PR_BODY", GOOD_BODY)
    code = pr_guard.main(["--base", "main", "--head", "HEAD", "--branch", "feature/add-y"])
    assert code == 1  # source changed, no test changed
