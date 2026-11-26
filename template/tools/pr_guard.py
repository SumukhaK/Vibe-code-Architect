"""Deterministic pull-request guardrails.

Runs in CI on every pull request. Each check is something a script can verify in
seconds, so no reviewer (human or model) should ever spend attention on it:

* the branch follows ``feature/`` / ``bugfix/`` / ``upkeep/`` naming;
* the change is small enough to review (surgical changes);
* source changes come with test changes (TDD), or an explicit, visible reason;
* the PR links the issue it implements (goal-driven execution);
* the PR carries verification evidence, not just a diff;
* guardrail files are only changed on ``upkeep/`` branches, so a feature PR
  cannot quietly loosen the rules it is judged by.

Configuration lives in ``guardrails.toml``. Standard library only.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

_ISSUE_LINK = re.compile(r"\b(close[sd]?|fix(e[sd])?|resolve[sd]?)\s+#\d+\b", re.IGNORECASE)
_NO_TESTS = re.compile(r"^No tests:\s*(\S.*)$", re.IGNORECASE | re.MULTILINE)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_RENAME = re.compile(r"\{[^{}]* => ([^{}]*)\}")


@dataclass(frozen=True)
class Config:
    branch_pattern: str
    max_changed_lines: int
    max_changed_files: int
    size_ignore_globs: tuple[str, ...]
    source_globs: tuple[str, ...]
    test_globs: tuple[str, ...]
    protected_globs: tuple[str, ...]
    guardrail_branch_prefix: str


@dataclass(frozen=True)
class Change:
    path: str
    added: int
    deleted: int


def load_config(path: Path) -> Config:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    pr, tests = data["pr"], data["tests"]
    return Config(
        branch_pattern=pr["branch_pattern"],
        max_changed_lines=int(pr["max_changed_lines"]),
        max_changed_files=int(pr["max_changed_files"]),
        size_ignore_globs=tuple(pr.get("size_ignore_globs", ())),
        source_globs=tuple(tests["source_globs"]),
        test_globs=tuple(tests["test_globs"]),
        protected_globs=tuple(pr.get("protected_globs", ())),
        guardrail_branch_prefix=pr.get("guardrail_branch_prefix", "upkeep/"),
    )


def _glob_regex(pattern: str) -> re.Pattern[str]:
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def matches(path: str, globs: tuple[str, ...]) -> bool:
    return any(_glob_regex(glob).match(path) for glob in globs)


def parse_numstat(text: str) -> list[Change]:
    changes = []
    for line in text.splitlines():
        if not line.strip():
            continue
        added, deleted, path = line.split("\t", 2)
        path = _RENAME.sub(r"\1", path).split(" => ")[-1].replace("//", "/")
        changes.append(
            Change(path, 0 if added == "-" else int(added), 0 if deleted == "-" else int(deleted))
        )
    return changes


def check_branch(branch: str, config: Config) -> list[str]:
    if re.match(config.branch_pattern, branch):
        return []
    return [
        f"Branch '{branch}' does not match {config.branch_pattern}. "
        "Use feature/<task>, bugfix/<task> or upkeep/<task>."
    ]


def check_size(changes: list[Change], config: Config) -> list[str]:
    counted = [c for c in changes if not matches(c.path, config.size_ignore_globs)]
    lines = sum(c.added + c.deleted for c in counted)
    problems = []
    if lines > config.max_changed_lines:
        problems.append(
            f"{lines} changed lines; the limit is {config.max_changed_lines}. "
            "Split the work into smaller PRs."
        )
    if len(counted) > config.max_changed_files:
        problems.append(
            f"{len(counted)} files changed; the limit is {config.max_changed_files}. "
            "Split the work into smaller PRs."
        )
    return problems


def check_tests(paths: list[str], body: str, config: Config) -> list[str]:
    touches_source = any(matches(p, config.source_globs) for p in paths)
    touches_tests = any(matches(p, config.test_globs) for p in paths)
    if not touches_source or touches_tests or _NO_TESTS.search(body):
        return []
    return [
        "Source changed but no test changed. Write the failing test first (TDD), "
        "or add a line 'No tests: <reason>' to the PR body for the reviewer to judge."
    ]


def check_issue_link(body: str) -> list[str]:
    if _ISSUE_LINK.search(body):
        return []
    return ["Link the issue this PR implements, e.g. 'Closes #12'."]


def check_verification(body: str) -> list[str]:
    match = re.search(r"^##\s+Verification\s*$(.*?)(?=^##\s|\Z)", body, re.MULTILINE | re.DOTALL)
    content = _COMMENT.sub("", match.group(1)).strip() if match else ""
    if content:
        return []
    return [
        "The '## Verification' section is empty. Show proof the change works: test output, "
        "a failing-then-passing test, screenshots or a CI artifact link — not just the diff."
    ]


def check_protected(paths: list[str], branch: str, config: Config) -> list[str]:
    if branch.startswith(config.guardrail_branch_prefix):
        return []
    touched = sorted(p for p in paths if matches(p, config.protected_globs))
    if not touched:
        return []
    return ["Guardrail files can only change on an upkeep/ branch: " + ", ".join(touched)]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True, help="base ref, e.g. origin/main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--branch", required=True, help="the PR's head branch name")
    parser.add_argument("--config", default="guardrails.toml")
    args = parser.parse_args(argv)

    config = load_config(Path(args.config))
    # The body arrives through an environment variable, never interpolated into a shell.
    body = os.environ.get("PR_BODY", "")
    changes = parse_numstat(_git("diff", "--numstat", f"{args.base}...{args.head}"))
    paths = [c.path for c in changes]

    problems = [
        *check_branch(args.branch, config),
        *check_size(changes, config),
        *check_tests(paths, body, config),
        *check_issue_link(body),
        *check_verification(body),
        *check_protected(paths, args.branch, config),
    ]
    for problem in problems:
        print(f"::error::{problem}")
    if not problems:
        print("All PR guardrails passed.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
