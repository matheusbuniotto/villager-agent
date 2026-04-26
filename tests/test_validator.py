from __future__ import annotations

import subprocess
from typing import Any


from app.schemas import RepoCommands, RepoPaths, RepoProfile, RepoRules
from app.validator import Validator


def _make_profile(**kwargs: Any) -> RepoProfile:
    defaults = {
        "repo_name": "example",
        "team_name": "platform",
        "language": "python",
        "build_system": "uv",
        "commands": RepoCommands(install="uv sync", lint="ruff check .", test="pytest"),
        "paths": RepoPaths(
            owned=["app/", "tests/"],
            sensitive=[".github/"],
            forbidden=["secrets/", "runs/"],
        ),
        "rules": RepoRules(),
        "pr": {"template": "standard"},
    }
    defaults.update(kwargs)
    return RepoProfile(**defaults)


_PATH_PREFIX = (
    "export PATH=/usr/local/go/bin:/usr/local/bin:"
    "/root/.cargo/bin:/root/.nvm/versions/node/*/bin:$PATH && "
)


class FakeCommandRunner:
    def __init__(self, responses: dict[str, tuple[int, str, str]]) -> None:
        self.responses = responses
        self.commands: list[list[str]] = []

    def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        # Normalise away the PATH prefix injected by _docker_exec so test
        # fixture keys don't need to include it.
        normalised = [
            part.replace(_PATH_PREFIX, "", 1) if _PATH_PREFIX in part else part
            for part in command
        ]
        key = " ".join(normalised)
        exit_code, stdout, stderr = self.responses.get(key, (0, "", ""))
        if exit_code != 0:
            exc = subprocess.CalledProcessError(exit_code, command, output=stdout, stderr=stderr)
            raise exc
        return subprocess.CompletedProcess(
            args=command, returncode=exit_code, stdout=stdout, stderr=stderr
        )


def test_all_passes() -> None:
    runner = FakeCommandRunner(
        {
            "docker exec villager-test sh -lc cd /workspace/repo && git ls-files": (
                0,
                "app/main.py\ntests/test_main.py\n",
                "",
            ),
            "docker exec villager-test sh -lc cd /workspace/repo && ruff check .": (
                0,
                "All checks passed\n",
                "",
            ),
            "docker exec villager-test sh -lc cd /workspace/repo && pytest": (
                0,
                "3 passed\n",
                "",
            ),
        }
    )
    validator = Validator(runner=runner)
    profile = _make_profile()

    report = validator.validate("villager-test", profile, "task-001")

    assert report.status == "pass"
    assert report.summary == "All validation checks passed."
    assert report.recommended_decision == "accept"
    assert all(c.status == "pass" for c in report.mechanical_checks)
    assert all(c.status == "pass" for c in report.policy_checks)


def test_forbidden_paths_trigger_fail_escalate() -> None:
    runner = FakeCommandRunner(
        {
            "docker exec villager-test sh -lc cd /workspace/repo && git ls-files": (
                0,
                "app/main.py\nsecrets/creds.yaml\n",
                "",
            ),
            "docker exec villager-test sh -lc cd /workspace/repo && ruff check .": (
                0,
                "",
                "",
            ),
            "docker exec villager-test sh -lc cd /workspace/repo && pytest": (
                0,
                "",
                "",
            ),
        }
    )
    validator = Validator(runner=runner)
    profile = _make_profile()

    report = validator.validate("villager-test", profile, "task-001")

    assert report.status == "fail_escalate"
    assert report.recommended_decision == "escalate"
    forbidden_check = next(c for c in report.policy_checks if c.name == "forbidden_paths_touched")
    assert forbidden_check.status == "fail"
    assert "secrets/creds.yaml" in (forbidden_check.reason or "")


def test_sensitive_paths_warning() -> None:
    runner = FakeCommandRunner(
        {
            "docker exec villager-test sh -lc cd /workspace/repo && git ls-files": (
                0,
                "app/main.py\n.github/workflows/ci.yml\n",
                "",
            ),
            "docker exec villager-test sh -lc cd /workspace/repo && ruff check .": (
                0,
                "",
                "",
            ),
            "docker exec villager-test sh -lc cd /workspace/repo && pytest": (
                0,
                "",
                "",
            ),
        }
    )
    validator = Validator(runner=runner)
    profile = _make_profile()

    report = validator.validate("villager-test", profile, "task-001")

    assert report.status == "pass_with_warnings"
    sensitive_check = next(c for c in report.policy_checks if c.name == "sensitive_paths_touched")
    assert sensitive_check.status == "warning"


def test_lint_failure_triggers_retryable() -> None:
    runner = FakeCommandRunner(
        {
            "docker exec villager-test sh -lc cd /workspace/repo && git ls-files": (
                0,
                "app/main.py\n",
                "",
            ),
            "docker exec villager-test sh -lc cd /workspace/repo && ruff check .": (
                1,
                "",
                "app/main.py:1:1: E501 line too long",
            ),
            "docker exec villager-test sh -lc cd /workspace/repo && pytest": (
                0,
                "",
                "",
            ),
        }
    )
    validator = Validator(runner=runner)
    profile = _make_profile()

    report = validator.validate("villager-test", profile, "task-001")

    assert report.status == "fail_retryable"
    assert report.recommended_decision == "retry"
    lint_check = next(c for c in report.mechanical_checks if c.name == "lint")
    assert lint_check.status == "fail"


def test_test_failure_triggers_retryable() -> None:
    runner = FakeCommandRunner(
        {
            "docker exec villager-test sh -lc cd /workspace/repo && git ls-files": (
                0,
                "app/main.py\n",
                "",
            ),
            "docker exec villager-test sh -lc cd /workspace/repo && ruff check .": (
                0,
                "",
                "",
            ),
            "docker exec villager-test sh -lc cd /workspace/repo && pytest": (
                1,
                "",
                "1 failed",
            ),
        }
    )
    validator = Validator(runner=runner)
    profile = _make_profile()

    report = validator.validate("villager-test", profile, "task-001")

    assert report.status == "fail_retryable"
    test_check = next(c for c in report.mechanical_checks if c.name == "test")
    assert test_check.status == "fail"


def test_git_ls_files_fallback_to_find() -> None:
    runner = FakeCommandRunner(
        {
            "docker exec villager-test sh -lc cd /workspace/repo && git ls-files": (
                128,
                "",
                "not a git repository",
            ),
            "docker exec villager-test sh -lc find /workspace/repo -type f | sed 's|/workspace/repo/||'": (
                0,
                "app/main.py\n",
                "",
            ),
            "docker exec villager-test sh -lc cd /workspace/repo && ruff check .": (
                0,
                "",
                "",
            ),
            "docker exec villager-test sh -lc cd /workspace/repo && pytest": (
                0,
                "",
                "",
            ),
        }
    )
    validator = Validator(runner=runner)
    profile = _make_profile()

    report = validator.validate("villager-test", profile, "task-001")

    assert report.status == "pass"
