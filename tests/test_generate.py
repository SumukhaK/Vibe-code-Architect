"""Generate real projects from the template and check what each stack gets."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def generate(tmp_path: Path, stacks: list[str]) -> Path:
    destination = tmp_path / "project"
    data = [
        "--data", "project_name=Demo App",
        "--data", "description=A demo.",
        "--data", "owner=octocat",
        "--data", f"stacks={stacks!r}".replace("'", '"'),
    ]
    subprocess.run(
        [sys.executable, "-m", "copier", "copy", "--trust", "--defaults", "--vcs-ref", "HEAD",
         *data, str(ROOT), str(destination)],
        check=True, capture_output=True, text=True,
    )
    return destination


CORE = [
    "AGENTS.md",
    "README.md",
    "guardrails.toml",
    ".jscpd.json",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/task.yml",
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/workflows/guardrails.yml",
    "docs/PRD.md",
    "docs/TECHNICAL.md",
    "docs/adr/0001-record-decisions.md",
    "docs/corrections.md",
    "docs/CODEMAP.md",
    "prompts/task.md",
    "prompts/review.md",
    "prompts/changes.md",
    "tools/pr_guard.py",
    "tools/codemap.py",
    "tools/protect_main.sh",
]
PYTHON = [
    "pyproject.toml",
    "src/demo_app/__init__.py",
    "src/demo_app/domain/__init__.py",
    "tests/test_smoke.py",
    "tools/red_green.py",
    ".github/workflows/python.yml",
]
ANDROID = [
    "config/detekt/detekt.yml",
    "app/src/test/kotlin/dev/octocat/demoapp/architecture/ArchitectureTest.kt",
    "docs/android-setup.md",
    ".github/workflows/android.yml",
]


@pytest.mark.parametrize(
    "stacks, present, absent",
    [
        (["python"], CORE + PYTHON, ANDROID),
        (["kotlin-android"], CORE + ANDROID, PYTHON),
        (["python", "kotlin-android"], CORE + PYTHON + ANDROID, []),
    ],
)
def test_each_stack_gets_core_plus_only_its_overlays(tmp_path, stacks, present, absent):
    project = generate(tmp_path, stacks)
    assert [f for f in present if not (project / f).is_file()] == []
    assert [f for f in absent if (project / f).exists()] == []
    leftovers = [p for p in project.rglob("*") if "{" in p.name or p.suffix == ".jinja"]
    assert leftovers == []


def test_guardrails_config_matches_the_stacks(tmp_path):
    project = generate(tmp_path, ["python", "kotlin-android"])
    config = tomllib.loads((project / "guardrails.toml").read_text(encoding="utf-8"))
    assert "src/**" in config["tests"]["source_globs"]
    assert "**/src/main/**" in config["tests"]["source_globs"]
    assert config["codemap"]["roots"] == ["src", "app/src/main"]
    assert "pyproject.toml" in config["pr"]["protected_globs"]


def test_generated_code_map_is_already_current(tmp_path):
    project = generate(tmp_path, ["python"])
    result = subprocess.run(
        [sys.executable, "tools/codemap.py", "--check"], cwd=project, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout
    assert "src/demo_app/__init__.py" in (project / "docs/CODEMAP.md").read_text(encoding="utf-8")


def test_kotlin_package_is_rendered_into_the_architecture_test(tmp_path):
    project = generate(tmp_path, ["kotlin-android"])
    source = next(project.rglob("ArchitectureTest.kt")).read_text(encoding="utf-8")
    assert "package dev.octocat.demoapp.architecture" in source
    assert '"dev.octocat.demoapp.domain.."' in source


def test_protect_script_requires_the_stack_checks(tmp_path):
    script = (generate(tmp_path, ["python"]) / "tools/protect_main.sh").read_text(encoding="utf-8")
    assert '"Python checks"' in script and "Android checks" not in script
