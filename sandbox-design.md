# Villager — Sandbox Design

## One-sentence definition

The Sandbox is the disposable Docker-based workspace where Villager clones a repo, applies a bounded change, runs validation, exports artifacts, and then destroys the environment.

---

# 1. Real goal

The sandbox exists for 3 reasons:
- make runs reproducible
- limit blast radius
- keep execution and validation in the same environment

That is enough.
Do not make this more magical than it is.

---

# 2. Grug design stance

For v1, the sandbox should be:
- one Docker container per run
- one cloned repo per run
- one work branch per run
- one artifact export step
- then destroy everything

Do not start with:
- nested sandboxes
- VM orchestration
- Kubernetes jobs
- persistent workspaces
- remote dev environments

**One boring container is good.**

---

# 3. What the sandbox must do

A valid sandbox should be able to:
1. start from a known image
2. clone the target repo
3. checkout the base branch
4. create a work branch
5. receive task/spec/profile context
6. run install/validation commands
7. allow the executor to inspect and edit code
8. export logs and artifacts
9. be destroyed cleanly

If it can do that, it is enough for v1.

---

# 4. Minimal lifecycle

```text
Choose image
  -> Create container
  -> Clone repo
  -> Checkout base branch
  -> Create work branch
  -> Inject context files
  -> Run executor
  -> Run validators
  -> Export artifacts
  -> Destroy container
```

This is the whole thing.

---

# 5. Recommended lifecycle in detail

## Step 1: Choose image
Pick a base image based on repo language/build system.

### V1 recommendation
Support only a few image families:
- `python-worker`
- `node-worker`
- maybe `polyglot-worker`

Do not build one image per repo yet.

---

## Step 2: Create container
Start a fresh ephemeral container with:
- resource limits
- working directory
- temporary run id
- no persistent state

### Rule
Every run starts clean.
No reusing dirty containers.

---

## Step 3: Clone repo
Inside the container:
- clone target repo
- checkout the configured base branch

### Why clone fresh?
Because reused workspaces create weird failures and trust problems.

---

## Step 4: Create work branch
Create a branch name from repo profile or default convention.

### Example
`villager/BILL-142-empty-coupon-validation`

### Rule
The sandbox should never work directly on the base branch.

---

## Step 5: Inject context
Make these available inside the sandbox:
- `TaskPacket`
- `ExecutionSpec`
- `RepoProfile`
- run metadata

### Simple approach
Write them as files into a known directory like:
`/.villager/`

Example:
- `/.villager/task-packet.yaml`
- `/.villager/execution-spec.yaml`
- `/.villager/repo-profile.yaml`

This is simple and debuggable.

---

## Step 6: Run executor
The executor inspects the repo and makes bounded code changes.

### Important boundary
The executor works inside the sandbox.
The harness still owns the decisions outside it.

---

## Step 7: Run validators
Run repo-aware commands in the same environment.

### Why same environment?
Because the code should be validated in the same place where it was changed.

### Typical commands
From `RepoProfile.commands`:
- install
- lint
- test
- typecheck

---

## Step 8: Export artifacts
Before destroying the sandbox, export:
- diff patch
- changed files list
- command log
- validation outputs
- PR body draft
- run metadata

### Rule
If an artifact matters, export it before teardown.

---

## Step 9: Destroy container
Remove the sandbox after artifacts are safely stored.

### Rule
No persistent state should live only inside the container.

---

# 6. What should live inside vs outside the sandbox

## Inside
- repo clone
- branch checkout
- code edits
- install/build/test commands
- temporary execution files

## Outside
- lifecycle state
- retry count
- final artifacts
- validation reports
- PR metadata
- run history

## Rule
The sandbox is for execution.
The system of record lives outside.

---

# 7. Filesystem layout recommendation

Keep it boring.

## Example inside container
```text
/workspace/repo/             # cloned repo
/workspace/artifacts/        # temp artifacts before export
/.villager/task-packet.yaml
/.villager/execution-spec.yaml
/.villager/repo-profile.yaml
/.villager/run-metadata.yaml
```

This is enough.

---

# 8. Image strategy

## Option A: one generic image
Pros:
- fewer images to manage

Cons:
- slower bootstrap
- more setup variability

## Option B: language-family images
Pros:
- better speed
- more predictable environment
- cleaner command support

Cons:
- a few more images to maintain

## Recommendation
Use **Option B**.

For v1, support only 2-3 image families.
That is the sweet spot.

---

# 9. Credentials model

Keep this strict.

## Sandbox may need credentials for:
- cloning private repos
- pushing a branch
- opening a PR
- maybe reading package registries

## Recommendation for v1
Inject only the minimum credentials needed for the run.

### Prefer
- short-lived tokens
- repo-scoped permissions
- no broad personal credentials

### Avoid
- long-lived full-access tokens inside the container
- credentials written permanently into repo files

## Simpler split
If possible:
- sandbox gets repo read/write and package read only
- PR creation can happen outside sandbox in the harness

That keeps secrets exposure lower.

---

# 10. Network policy

Keep it simple.

## V1 recommendation
Allow network only for what is necessary:
- git clone/fetch/push
- package install if needed
- PR API if done inside sandbox

If you can move PR creation outside, even better.

## Rule
Default to limited network, not “open internet because convenient.”

Do not overbuild firewall complexity for v1, but do not ignore network completely.

---

# 11. Resource and time limits

Every sandbox should have explicit bounds.

## Suggested limits
- max CPU
- max memory
- max disk use if practical
- max runtime per attempt

## Why
Without limits, loops get expensive and failures get messy.

## Grug rule
A stuck container is not intelligence. It is a timeout.

---

# 12. Branch handling

Keep branch behavior deterministic.

## V1 branch flow
1. checkout base branch
2. create work branch
3. commit changes if needed
4. push branch if run is accepted for draft PR

## Rules
- never edit on base branch
- branch names should be predictable
- branch naming should come from repo profile or default

---

# 13. Artifact export

This part matters a lot.

## Export at minimum
- `diff.patch`
- `changed-files.json`
- `command-log.txt`
- `validation-report.json`
- `pr-body.md`
- `run-summary.json`

## Recommendation
Export artifacts to a run-scoped directory outside the container.

Example:
```text
runs/
  run-2026-04-24-001/
    diff.patch
    command-log.txt
    validation-report.json
    pr-body.md
```

This is very easy to inspect.

---

# 14. Failure modes

## Retryable sandbox failures
- transient git failure
- package registry timeout
- temporary auth issue
- container startup hiccup

## Escalate failures
- repo image mismatch that cannot run required commands
- invalid repo profile commands
- missing required credentials
- repeated bootstrap failures

## Rule
Separate sandbox failures from code failures.
Do not spend code-fix retries on infrastructure problems.

---

# 15. What not to support in v1

Do not support yet:
- nested repos
- multi-repo task execution
- docker-in-docker builds unless absolutely required
- background long-running services orchestration
- interactive manual debugging inside live sandboxes
- sandbox resume from checkpoint

All of that is backlog.

---

# 16. Suggested simple implementation shape

You likely need one `SandboxManager` module with functions like:
- `select_image(repo_profile)`
- `create_run_workspace(run_id)`
- `start_container(...)`
- `clone_repo(...)`
- `prepare_branch(...)`
- `inject_context(...)`
- `run_command(...)`
- `export_artifacts(...)`
- `destroy_container(...)`

That is enough.

No workflow engine needed.

---

# 17. Opinionated v1 recommendation

For v1, do this:
- one container per run
- clone repo fresh each time
- use 2-3 language-family images
- keep context as files in `/.villager/`
- export all artifacts to a host-side run directory
- destroy container every run
- keep PR creation outside sandbox if possible

This is simple, legible, and safe enough.

---

# 18. Grug conclusion

The sandbox should not be clever.
It should be boring.

**Fresh container in. Code work happens. Evidence out. Container dies.**

That is the right v1 sandbox.

---

# 19. Next doc

Best next document:

**`interfaces-and-services.md`**

Why:
Now that runtime behavior is defined, the next step is to decide the internal module boundaries of the application itself.