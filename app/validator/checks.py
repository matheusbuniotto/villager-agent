from __future__ import annotations

import subprocess
from typing import Protocol

from app.schemas import RepoProfile, ValidationCheck, ValidationReport


class CommandRunner(Protocol):
    def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        """Execute a command and return its completed process."""


class SubprocessCommandRunner:
    def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, check=True, capture_output=True, text=True)


class Validator:
    """Run validation checks against a sandbox container."""

    def __init__(self, runner: CommandRunner | None = None) -> None:
        self._runner = runner or SubprocessCommandRunner()

    def _docker_exec(
        self, container_name: str, shell_command: str
    ) -> subprocess.CompletedProcess[str]:
        patched = (
            "export PATH=/usr/local/go/bin:/usr/local/bin:"
            "/root/.cargo/bin:/root/.nvm/versions/node/*/bin:$PATH && "
            + shell_command
        )
        return self._runner.run(["docker", "exec", container_name, "sh", "-lc", patched])

    def _list_repo_files(self, container_name: str) -> list[str]:
        """List all files under /workspace/repo in the container."""
        try:
            result = self._docker_exec(
                container_name,
                "cd /workspace/repo && git ls-files",
            )
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except subprocess.CalledProcessError:
            # Fallback to find if not a git repo
            result = self._docker_exec(
                container_name,
                "find /workspace/repo -type f | sed 's|/workspace/repo/||'",
            )
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _run_command_in_repo(
        self, container_name: str, command: str
    ) -> subprocess.CompletedProcess[str] | None:
        """Run a shell command inside the container at /workspace/repo."""
        try:
            return self._docker_exec(container_name, f"cd /workspace/repo && {command}")
        except subprocess.CalledProcessError as exc:
            return exc  # type: ignore[return-value]

    def validate(
        self,
        container_name: str,
        profile: RepoProfile,
        task_id: str,
    ) -> ValidationReport:
        """Run all validation checks and return a report."""
        report_id = f"validation-{task_id}"
        mechanical_checks: list[ValidationCheck] = []
        policy_checks: list[ValidationCheck] = []
        warnings: list[str] = []
        failures: list[str] = []

        # --- Path policy checks ---
        files = self._list_repo_files(container_name)

        forbidden_touched = [
            f
            for f in files
            if any(
                f.startswith(p.strip("/") + "/") or f == p.strip("/")
                for p in profile.paths.forbidden
            )
        ]
        sensitive_touched = [
            f
            for f in files
            if any(
                f.startswith(p.strip("/") + "/") or f == p.strip("/")
                for p in profile.paths.sensitive
            )
        ]

        policy_checks.append(
            ValidationCheck(
                name="forbidden_paths_touched",
                status="pass" if not forbidden_touched else "fail",
                reason=(
                    None
                    if not forbidden_touched
                    else f"Touched forbidden paths: {forbidden_touched}"
                ),
            )
        )
        policy_checks.append(
            ValidationCheck(
                name="sensitive_paths_touched",
                status="pass" if not sensitive_touched else "warning",
                reason=(
                    None
                    if not sensitive_touched
                    else f"Touched sensitive paths: {sensitive_touched}"
                ),
            )
        )

        if forbidden_touched:
            failures.append(f"Forbidden paths touched: {forbidden_touched}")
        if sensitive_touched:
            warnings.append(f"Sensitive paths touched: {sensitive_touched}")

        # --- Mechanical checks: lint and test ---
        for check_name, command in (
            ("lint", profile.commands.lint),
            ("test", profile.commands.test),
        ):
            result = self._run_command_in_repo(container_name, command)
            if result is None:
                mechanical_checks.append(
                    ValidationCheck(
                        name=check_name,
                        status="skipped",
                        reason=f"Command '{command}' failed to execute",
                    )
                )
                skipped = f"{check_name} command failed to execute"
                warnings.append(skipped)
            elif isinstance(result, subprocess.CalledProcessError):
                mechanical_checks.append(
                    ValidationCheck(
                        name=check_name,
                        status="fail",
                        reason=result.stderr.strip()[:200] or f"Exit code {result.returncode}",
                    )
                )
                failures.append(f"{check_name} failed")
            else:
                mechanical_checks.append(
                    ValidationCheck(
                        name=check_name,
                        status="pass",
                    )
                )

        # --- Determine overall status ---
        if failures:
            status = "fail_escalate" if forbidden_touched else "fail_retryable"
            summary = f"Validation failed with {len(failures)} failure(s)."
            recommended = "escalate" if forbidden_touched else "retry"
        elif warnings:
            status = "pass_with_warnings"
            summary = f"Validation passed with {len(warnings)} warning(s)."
            recommended = "accept"
        else:
            status = "pass"
            summary = "All validation checks passed."
            recommended = "accept"

        return ValidationReport(
            report_id=report_id,
            task_id=task_id,
            status=status,  # type: ignore[arg-type]
            summary=summary,
            mechanical_checks=mechanical_checks,
            policy_checks=policy_checks,
            spec_alignment_checks=[],
            warnings=warnings,
            failures=failures,
            recommended_decision=recommended,  # type: ignore[arg-type]
        )
