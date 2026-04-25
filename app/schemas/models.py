from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


Priority = Literal["low", "medium", "high", "critical"]
RiskLevel = Literal["low", "medium", "high"]
ValidationStatus = Literal[
    "pass",
    "pass_with_warnings",
    "fail_retryable",
    "fail_escalate",
]
DecisionType = Literal["accept", "retry", "escalate", "wait_human"]
CheckStatus = Literal["pass", "fail", "warning", "skipped"]
RunState = Literal[
    "INTAKE",
    "SPEC_READY",
    "SANDBOX_READY",
    "EXECUTING",
    "VALIDATING",
    "REVIEW_READY",
    "PR_DRAFTED",
    "DONE",
    "FAILED_RETRYABLE",
    "FAILED_ESCALATE",
    "WAITING_HUMAN",
]

VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_RISK_LEVELS = {"low", "medium", "high"}
VALID_VALIDATION_STATUSES = {
    "pass",
    "pass_with_warnings",
    "fail_retryable",
    "fail_escalate",
}
VALID_DECISIONS = {"accept", "retry", "escalate", "wait_human"}
VALID_CHECK_STATUSES = {"pass", "fail", "warning", "skipped"}
VALID_RUN_STATES = {
    "INTAKE",
    "SPEC_READY",
    "SANDBOX_READY",
    "EXECUTING",
    "VALIDATING",
    "REVIEW_READY",
    "PR_DRAFTED",
    "DONE",
    "FAILED_RETRYABLE",
    "FAILED_ESCALATE",
    "WAITING_HUMAN",
}


def require_one_of(field_name: str, value: str, valid_values: set[str]) -> None:
    if value not in valid_values:
        allowed = ", ".join(sorted(valid_values))
        raise ValueError(f"{field_name} must be one of: {allowed}")


@dataclass(slots=True)
class RepoCommands:
    install: str
    lint: str
    test: str
    format: str | None = None
    typecheck: str | None = None
    build: str | None = None
    smoke: str | None = None


@dataclass(slots=True)
class RepoPaths:
    owned: list[str]
    sensitive: list[str]
    forbidden: list[str]
    test_locations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RepoRules:
    require_tests_for_behavior_change: bool = True
    block_dependency_changes_without_reason: bool = True
    require_human_approval_for_migrations: bool = True
    forbid_generated_code_edits: bool = True
    max_changed_files_before_warning: int | None = None
    max_diff_lines_before_warning: int | None = None


@dataclass(slots=True)
class PRSettings:
    template: str
    labels: list[str] = field(default_factory=list)
    reviewers: list[str] = field(default_factory=list)
    required_sections: list[str] = field(default_factory=list)
    draft_by_default: bool = True
    branch_prefix: str | None = None


@dataclass(slots=True)
class RepoExamples:
    good_prs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RepoProfile:
    repo_name: str
    team_name: str
    language: str
    build_system: str
    commands: RepoCommands
    paths: RepoPaths
    rules: RepoRules
    pr: PRSettings
    dependencies: list[str] = field(default_factory=list)
    service_type: str | None = None
    deployment_sensitivity: str | None = None
    reviewer_groups: list[str] = field(default_factory=list)
    examples: RepoExamples | None = None
    known_gotchas: list[str] = field(default_factory=list)
    environment_notes: list[str] = field(default_factory=list)
    agent_instructions: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoProfile":
        return cls(
            repo_name=data["repo_name"],
            team_name=data["team_name"],
            language=data["language"],
            build_system=data["build_system"],
            commands=RepoCommands(**data["commands"]),
            paths=RepoPaths(**data["paths"]),
            rules=RepoRules(**data["rules"]),
            pr=PRSettings(**data["pr"]),
            dependencies=data.get("dependencies", []),
            service_type=data.get("service_type"),
            deployment_sensitivity=data.get("deployment_sensitivity"),
            reviewer_groups=data.get("reviewer_groups", []),
            examples=RepoExamples(**data["examples"]) if data.get("examples") else None,
            known_gotchas=data.get("known_gotchas", []),
            environment_notes=data.get("environment_notes", []),
            agent_instructions=data.get("agent_instructions", []),
        )


@dataclass(slots=True)
class TaskPacket:
    task_id: str
    source: str
    source_issue_key: str
    title: str
    description: str
    repo: str
    requested_outcome: str
    priority: Priority
    risk_level: RiskLevel
    labels: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    assignee: str | None = None
    reporter: str | None = None
    linked_services: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    ambiguity_flags: list[str] = field(default_factory=list)
    comments_summary: str | None = None
    attachments: list[str] = field(default_factory=list)
    team: str | None = None
    target_branch: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_one_of("priority", self.priority, VALID_PRIORITIES)
        require_one_of("risk_level", self.risk_level, VALID_RISK_LEVELS)


@dataclass(slots=True)
class ExecutionSpec:
    spec_id: str
    task_id: str
    problem_statement: str
    scope_in: list[str] = field(default_factory=list)
    scope_out: list[str] = field(default_factory=list)
    target_areas: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    validation_steps: list[str] = field(default_factory=list)
    artifacts_required: list[str] = field(default_factory=list)
    stop_conditions: list[str] = field(default_factory=list)
    escalation_conditions: list[str] = field(default_factory=list)
    implementation_notes: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    suggested_plan: list[str] = field(default_factory=list)
    max_files_to_change: int | None = None
    test_expectations: list[str] = field(default_factory=list)
    review_focus: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ValidationCheck:
    name: str
    status: CheckStatus
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_one_of("status", self.status, VALID_CHECK_STATUSES)


@dataclass(slots=True)
class ValidationReport:
    report_id: str
    task_id: str
    status: ValidationStatus
    summary: str
    mechanical_checks: list[ValidationCheck] = field(default_factory=list)
    policy_checks: list[ValidationCheck] = field(default_factory=list)
    spec_alignment_checks: list[ValidationCheck] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    skipped_checks: list[str] = field(default_factory=list)
    review_notes: list[str] = field(default_factory=list)
    confidence_signals: dict[str, Any] = field(default_factory=dict)
    recommended_decision: DecisionType | None = None

    def __post_init__(self) -> None:
        require_one_of("status", self.status, VALID_VALIDATION_STATUSES)
        if self.recommended_decision is not None:
            require_one_of(
                "recommended_decision",
                self.recommended_decision,
                VALID_DECISIONS,
            )


@dataclass(slots=True)
class ReviewDecision:
    decision_id: str
    task_id: str
    decision: DecisionType
    reason: str
    next_action: str
    retry_count: int = 0
    human_input_required: bool = False
    blocking_issues: list[str] = field(default_factory=list)
    notes_for_retry: list[str] = field(default_factory=list)
    notes_for_human: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        require_one_of("decision", self.decision, VALID_DECISIONS)


@dataclass(slots=True)
class ArtifactBundle:
    artifact_id: str
    task_id: str
    diff_patch: str
    execution_summary: str
    validation_report_ref: str
    pr_body: str
    changed_files: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    command_log: list[str] = field(default_factory=list)
    test_results: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    review_annotations: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    sandbox_info: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RunRecord:
    run_id: str
    task_id: str
    repo_name: str
    state: RunState
    created_at: datetime
    updated_at: datetime
    retry_count: int = 0
    task_packet_ref: str | None = None
    profile_ref: str | None = None
    spec_ref: str | None = None
    validation_report_ref: str | None = None
    review_decision_ref: str | None = None
    artifact_bundle_ref: str | None = None
    final_outcome: str | None = None

    def __post_init__(self) -> None:
        require_one_of("state", self.state, VALID_RUN_STATES)
