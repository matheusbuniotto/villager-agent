# Villager — Tech Stack

## One-sentence decision

Villager v1 will be a single Python app with a simple orchestrator, one coding agent, Docker-based ephemeral sandboxes, Postgres for state, and plain YAML/Markdown files for repo profiles and artifacts.

---

# 1. Grug rule

Use the most boring stack that can ship the first ugly working path.

Do not optimize for:
- agent framework prestige
- event-driven architecture purity
- cloud-native cleverness
- multi-agent orchestration tricks

Optimize for:
- easy to run
- easy to debug
- easy to change
- small number of dependencies

---

# 2. Recommended stack at a glance

## Language
**Python 3.12**

Why:
- best library ecosystem for LLM/app glue
- easiest for agent + harness + CLI + Docker orchestration
- simple JSON/YAML handling
- good enough for v1 concurrency needs

---

## App shape
**One Python app**

Recommended style:
- Typer for CLI / entrypoints
- plain modules for business logic
- no microservices
- no heavy workflow engine

---

## Agent layer
**Decision (2026-04-25): deepagents**

Evaluated: PydanticAI, deepagents (langchain-ai), smolagents (HuggingFace).

Chosen deepagents because:
- built-in coding tools: `read_file`, `write_file`, `edit_file`, `grep`, `glob`, `execute` — no need to write tool wrappers
- `SandboxBackendProtocol` designed for agent + sandbox use case
- dep weight (~50MB LangChain/LangGraph stack) acceptable for MVP

Trade-off accepted: pulls in LangGraph as runtime. Orchestration lifecycle (retries, state transitions) stays in plain Python — deepagents owns only the executor step.

Reversibility: medium cost. Executor is one module (`app/executor/`); swapping back to PydanticAI means rewriting that module and its tools.

### Use it for
- executor agent (VIL-011): reads spec, writes code changes in sandbox

### Do not use it for
- lifecycle state machine
- retries
- orchestration logic

That stays in your code.

---

## LLM provider
**Start with OpenAI-compatible API abstraction**

Practical recommendation:
- use whatever model endpoint you already trust most
- keep provider behind one adapter

### V1 rule
One provider first.
Do not build multi-provider routing yet.

---

## Orchestration / harness
**Plain Python service code**

Use:
- simple service classes/functions
- explicit state transitions
- no LangGraph
- no Temporal
- no Prefect

### Why
The lifecycle is simple enough to own directly.
Workflow frameworks will add more ceremony than value in v1.

---

## Sandbox
**Docker SDK for Python + Docker CLI fallback**

Primary recommendation:
- use the Python Docker SDK for start/stop/logs/copy/archive operations

Fallback:
- shell out to `docker` CLI when simpler

### Why
This keeps sandbox orchestration local and boring.

---

## Git operations
**GitPython OR plain git CLI**

### Recommendation
Use **plain git CLI** first.

Why:
- fewer abstraction surprises
- easier to debug
- matches how you think about branches/remotes anyway

Use subprocess calls for:
- clone
- checkout
- branch create
- diff
- commit
- push

---

## State store
**Postgres**

Why:
- boring and reliable
- easy to query runs and states
- good enough for v1 and beyond

### ORM / DB layer
**SQLModel** or **SQLAlchemy Core**

### Recommendation
Use **SQLModel** if you want speed and readable models.
If you want maximum explicitness, SQLAlchemy Core is also fine.

Grug call:
**SQLModel** is a good balance.

---

## Artifact storage
**Local filesystem first**

Store run artifacts in:
- `runs/<run_id>/...`

Why:
- easiest to inspect
- easiest to debug
- no object storage complexity for v1

Later, this can move to S3 if needed.

---

## Queue / execution trigger
**Start with DB-backed polling or simple CLI/manual trigger**

### Recommendation
For first working version:
- manual CLI trigger
- optional JIRA poller later

Do not start with RabbitMQ/Kafka/SQS.

### Why
You need one working run first, not distributed queue sophistication.

---

## JIRA integration
**Atlassian Python API or plain REST wrapper**

### Recommendation
Use **plain REST wrapper with `httpx`**.

Why:
- less magic
- easy to control exact fields fetched
- one less opinionated dependency

---

## GitHub/GitLab integration
**Plain REST wrapper with `httpx`**

Why:
- draft PR creation is a small API surface
- no need for big SDK dependency yet

---

## Config / profiles
**YAML files**

Use for:
- repo profiles
- maybe environment-independent defaults

Libraries:
- `pydantic` for typed config models
- `PyYAML` or `ruamel.yaml` for loading

### Recommendation
Use **PyYAML + Pydantic**

Simple and enough.

---

## Schema layer
**Pydantic models**

Use for:
- `TaskPacket`
- `RepoProfile`
- `ExecutionSpec`
- `ValidationReport`
- `ReviewDecision`
- `ArtifactBundle`
- `RunRecord`

Why:
- typed contracts
- validation built-in
- great fit for agent IO too

---

## Web/API layer
### Recommendation
Skip API server at first if possible.

Start with:
- CLI entrypoint
- maybe simple background worker later

If you need API later:
- **FastAPI**

But do not start there unless it helps your real workflow.

---

## Logging
**structlog** or stdlib logging

### Recommendation
Use **stdlib logging** first.

If logs get messy later, switch to structlog.

Grug says:
If print/logging works, do not add logging architecture.

---

## Test framework
**pytest**

Use for:
- schema tests
- spec-builder tests
- validator tests
- orchestrator happy-path tests

No debate here.

---

## Lint / format / typecheck
Use:
- **ruff**
- **mypy**

Simple and standard.

---

## Packaging / env
**uv** or **poetry**

### Recommendation
Use **uv** if you want speed and simplicity.
If your default muscle memory is poetry, that is also okay.

Grug call:
**uv** is the simplest modern choice.

---

# 3. The opinionated v1 stack

If I were making the calls for Villager v1, I would choose:

- **Python 3.12**
- **uv**
- **Typer**
- **Pydantic**
- **PydanticAI**
- **httpx**
- **PyYAML**
- **Docker SDK for Python**
- **plain git CLI via subprocess**
- **SQLModel + Postgres**
- **local filesystem artifacts**
- **pytest**
- **ruff + mypy**

That is the stack.

---

# 4. What each tool is for

## Agent
- **PydanticAI**
- one executor agent
- optional spec-generation agent wrapper

## Harness/orchestrator
- plain Python modules/classes
- no framework

## Sandbox
- Docker SDK
- docker images per language family

## State
- Postgres + SQLModel

## External integrations
- httpx for JIRA + GitHub/GitLab APIs

## Contracts
- Pydantic models

## Repo personalization
- YAML repo profiles

## Triggering
- Typer CLI first

---

# 5. What we are explicitly NOT using in v1

Do not use:
- LangGraph (except as deepagents runtime — do not use LangGraph directly)
- CrewAI
- AutoGen
- Temporal
- Prefect
- Celery
- Kafka
- Redis queues unless needed later
- Kubernetes jobs
- vector DB for repo memory
- graph database for memory

Why:
All of these are more architecture than the MVP needs.

---

# 6. Minimal implementation shape

A real minimal starting app could look like this:

```text
villager/
  app/
    intake/
    spec_builder/
    orchestrator/
    sandbox/
    validator/
    pr_composer/
    state_store/
    schemas/
    main.py
  profiles/
  runs/
  tests/
```

And the first command could be:

```bash
villager run --jira BILL-142
```

That is enough to prove the architecture.

---

# 7. Option B we are NOT choosing

## Alternative
Use LangGraph + FastAPI + Celery + Redis + S3 + hosted sandbox infra.

## Why we are not choosing it
Because you do not need platform complexity before the first useful run exists.

Cost to reverse later from simple Python app -> more infra:
**low to medium**

Cost to simplify after overbuilding early:
**high**

---

# 8. First ugly artifact

The first ugly working version should:
1. accept a JIRA issue key from CLI
2. fetch issue details
3. load repo profile YAML
4. build an `ExecutionSpec`
5. start Docker sandbox
6. clone repo and create branch
7. run one executor pass
8. run validators
9. write artifacts to `runs/<run_id>/`
10. generate draft PR markdown

No web UI needed.
No queue needed.
No agent swarm needed.

---

# 9. Grug conclusion

The best v1 stack is the one that gets you to:

**one boring end-to-end run that actually works**

So the stack should be:
- Python
- typed models
- simple agent wrapper
- Docker
- Postgres
- YAML
- CLI

That is enough.

---

# 10. Next step

Best next document:

**`mvp-build-plan.md`**

Because now the architecture and stack are both defined, and the next move is to turn them into a build sequence.