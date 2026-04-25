# Villager — Visual Plan

This document uses simple diagrams to make the Villager system easier to reason about.

Use this as the “picture version” of:
- `architecture-plan.md`
- `schemas.md`
- `run-lifecycle.md`

---

# 1. System view

## Big picture

```mermaid
flowchart LR
    J[JIRA Tagged Task] --> N[Task Normalizer]
    N --> S[Spec Builder]
    P[Repo/Team Profile] --> S
    S --> H[Harness Orchestrator]
    H --> X[Sandbox Manager]
    X --> E[Executor Agent]
    E --> V[Validation Sensors]
    V --> H
    H --> R[Review Decision]
    R --> PR[Draft PR Composer]
    PR --> G[GitHub/GitLab Draft PR]
    H --> A[Artifacts / Logs / State]
```

## Read it like this
- JIRA gives the work
- normalization cleans the task
- spec builder turns it into bounded work
- harness controls the run
- sandbox gives safe execution
- executor does the coding
- validators check the result
- harness decides retry / human gate / PR draft

---

# 2. Responsibility boundaries

```mermaid
flowchart TB
    subgraph Agent
        E[Executor Agent]
    end

    subgraph Harness
        O[Orchestrator]
        L[Loop Controller]
        D[Decision Engine]
        M[Memory / State]
    end

    subgraph Sandbox
        C[Ephemeral Docker Container]
        W[Workspace / Repo Clone]
    end

    subgraph Sensors
        T[Tests]
        Y[Typecheck]
        I[Lint]
        P[Policy Checks]
        SR[Spec Review]
    end

    O --> E
    E --> C
    C --> W
    O --> T
    O --> Y
    O --> I
    O --> P
    O --> SR
    T --> D
    Y --> D
    I --> D
    P --> D
    SR --> D
    D --> L
    L --> O
    O --> M
```

## Key idea
The **agent writes**.
The **harness decides**.
The **sensors judge**.
The **sandbox contains**.

---

# 3. End-to-end happy path

```mermaid
sequenceDiagram
    participant J as JIRA
    participant N as Normalizer
    participant S as Spec Builder
    participant H as Harness
    participant X as Sandbox
    participant E as Executor
    participant V as Validators
    participant P as PR Composer

    J->>N: Tagged issue
    N->>S: TaskPacket
    S->>H: ExecutionSpec + RepoProfile
    H->>X: Prepare sandbox
    X->>E: Repo + branch + context
    E->>X: Code changes
    H->>V: Run checks
    V->>H: ValidationReport(pass)
    H->>P: Build PR package
    P->>H: Draft PR body
    H->>J: Link back / update status
```

---

# 4. Retry loop visual

```mermaid
flowchart TD
    A[Executor makes change] --> B[Validators run]
    B --> C{Checks pass?}
    C -- Yes --> D[Prepare PR draft]
    C -- No, retryable --> E[Harness builds RetryInstruction]
    E --> F[Executor retries with focused guidance]
    F --> B
    C -- No, high risk / ambiguous --> G[Human Gate or Escalation]
```

## Core rule
Do not do:
- raw log dump back into model
- infinite repair loop
- self-declared success

Do this instead:
- structured retry instruction
- capped retries
- harness-owned routing

---

# 5. Human gate visual

```mermaid
flowchart LR
    A[Validation / Policy Check] --> B{Needs human?}
    B -- No --> C[Continue run]
    B -- Yes --> D[Create HumanGateRequest]
    D --> E[Human reviews]
    E --> F{Decision}
    F -- Approve --> C
    F -- Clarify scope --> G[Update spec]
    G --> C
    F -- Reject --> H[Cancel / Escalate]
```

## Trigger examples
- migration needed
- sensitive path touched
- ambiguous acceptance criteria
- retry cap exceeded
- risky diff too large

---

# 6. State machine visual

```mermaid
stateDiagram-v2
    [*] --> INTAKE
    INTAKE --> SPEC_BUILDING
    SPEC_BUILDING --> SPEC_READY
    SPEC_BUILDING --> WAITING_HUMAN
    SPEC_BUILDING --> FAILED_ESCALATE

    SPEC_READY --> SANDBOX_PREPARING
    SANDBOX_PREPARING --> SANDBOX_READY
    SANDBOX_PREPARING --> FAILED_RETRYABLE

    SANDBOX_READY --> EXECUTING
    EXECUTING --> VALIDATING
    EXECUTING --> WAITING_HUMAN
    EXECUTING --> FAILED_RETRYABLE

    VALIDATING --> REVIEW_READY
    VALIDATING --> RETRYING
    VALIDATING --> WAITING_HUMAN
    VALIDATING --> FAILED_ESCALATE

    RETRYING --> EXECUTING
    RETRYING --> WAITING_HUMAN

    REVIEW_READY --> PR_DRAFTING
    PR_DRAFTING --> PR_DRAFTED
    PR_DRAFTED --> DONE

    WAITING_HUMAN --> SPEC_READY
    WAITING_HUMAN --> EXECUTING
    WAITING_HUMAN --> CANCELLED

    FAILED_RETRYABLE --> SANDBOX_PREPARING
    FAILED_RETRYABLE --> FAILED_ESCALATE
```

---

# 7. Data objects through the flow

```mermaid
flowchart LR
    TP[TaskPacket] --> ES[ExecutionSpec]
    RP[RepoProfile] --> ES
    ES --> ER[Executor Run]
    ER --> VR[ValidationReport]
    VR --> RD[ReviewDecision]
    RD --> AB[ArtifactBundle]
    AB --> PR[Draft PR]
```

## Meaning
- `TaskPacket` = normalized work intake
- `RepoProfile` = personalization layer
- `ExecutionSpec` = bounded contract for execution
- `ValidationReport` = evidence from sensors
- `ReviewDecision` = harness routing output
- `ArtifactBundle` = final exported package

---

# 8. Personalization model visual

```mermaid
flowchart TB
    RP[RepoProfile]

    RP --> A[Tooling Commands]
    RP --> B[Path Rules]
    RP --> C[Process Rules]
    RP --> D[Review Rules]
    RP --> E[Examples / Good PRs]

    A --> A1[test/lint/typecheck/build]
    B --> B1[owned/sensitive/forbidden]
    C --> C1[branch / labels / reviewers]
    D --> D1[human gates / risk thresholds]
    E --> E1[accepted implementation patterns]
```

## Why this matters
Personalization is not just “extra prompt context.”
It is operational behavior.

---

# 9. Sandbox run visual

```mermaid
flowchart TD
    A[Receive ExecutionSpec] --> B[Choose base image]
    B --> C[Create ephemeral workspace]
    C --> D[Clone repo]
    D --> E[Checkout base branch]
    E --> F[Create work branch]
    F --> G[Inject task/spec/profile]
    G --> H[Run executor]
    H --> I[Run validators]
    I --> J[Export artifacts]
    J --> K[Destroy container]
```

## Important properties
- ephemeral
- reproducible
- resource-bounded
- no persistent state inside container
- all evidence exported before teardown

---

# 10. Trust model visual

```mermaid
flowchart LR
    A[Agent says: I changed code] --> B[Harness says: prove it]
    B --> C[Tests / Lint / Typecheck]
    B --> D[Policy Checks]
    B --> E[Spec Alignment]
    C --> F[ValidationReport]
    D --> F
    E --> F
    F --> G{Good enough?}
    G -- Yes --> H[Draft PR]
    G -- No --> I[Retry or Human Gate]
```

## This is the product
Not just “AI writes code.”
The real product is:
**AI work that can be trusted enough to review quickly.**

---

# 11. Minimal v1 visual

If you want the simplest possible first implementation, think of it like this:

```mermaid
flowchart LR
    J[JIRA Ticket] --> S[ExecutionSpec]
    S --> X[Docker Sandbox]
    X --> E[Executor]
    E --> V[Tests/Lint]
    V --> D{Pass?}
    D -- Yes --> P[Draft PR]
    D -- No --> R[Retry up to 3x]
    R --> E
    R --> H[Human Gate]
```

## That is enough for v1
Do not overbuild before this runs.

---

# 12. Recommended operator dashboards later

```mermaid
flowchart TB
    O[Operator Dashboard]
    O --> A[Queued Runs]
    O --> B[Active Runs]
    O --> C[Waiting Human]
    O --> D[Failed Runs]
    O --> E[Completed Runs]
    O --> F[Validation Reports]
```

This is not required for day 1, but useful for operating the system once multiple runs exist.

---

# 13. Main design insight

If you remember only one visual, remember this:

```mermaid
flowchart LR
    Task[Task] --> Spec[Bounded Spec]
    Spec --> Sandbox[Safe Sandbox]
    Sandbox --> Code[Code Change]
    Code --> Validation[Validation Evidence]
    Validation --> Decision[Retry / Human / PR]
```

That is Villager in one line.

---

# 14. What to discuss next

Now that the flow is visual, the highest-value follow-up discussions are:

1. **Where exactly does spec generation happen?**
2. **What does the first RetryInstruction schema look like?**
3. **How should human gate UX work?**
4. **What is the minimum sandbox bootstrap contract?**
5. **What are the first repo profile fields to support in code?**

---

# 15. Recommended next artifact

Best next file:

**`diagrams/system-sequence.mmd`** and maybe separate Mermaid files per diagram.

Why:
- easier to edit than one long markdown file
- can be rendered in docs or CI later
- keeps architecture visuals reusable
