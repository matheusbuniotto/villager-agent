# Villager — Product Scope

## One-sentence product definition

Villager is a harnessed coding worker that takes a tagged JIRA ticket for a small software change, executes the work in an ephemeral repo-aware sandbox, validates the result, and produces a draft PR with evidence.

---

# 1. Real problem

Teams lose time on small engineering tasks that are:
- clear enough to execute
- annoying enough to delay
- important enough to still require review

The goal of Villager is not to replace engineers.
The goal is to reduce the cost of taking a small, bounded task from:

**ticket -> implementation -> validation -> draft PR**

---

# 2. Target user

## Primary user
A software team that wants help with repetitive, bounded coding work inside existing repos.

## First operator
You.

That matters because v1 should optimize for:
- speed of iteration
- simplicity of architecture
- strong observability
- easy manual intervention

Not enterprise complexity.

---

# 3. V1 product shape

Villager v1 is:
- one application with clean modules
- one executor agent
- one harness/orchestrator
- one ephemeral Docker sandbox per run
- fully automatic spec generation
- deterministic validation first
- draft PR output only

Villager v1 is not:
- a multi-agent swarm
- an auto-merge system
- a deployment system
- a broad autonomous engineer

---

# 4. Supported task types in v1

Villager v1 should support only **small, bounded engineering tasks**.

## In scope

### A. Small bug fixes
Examples:
- validation bug
- wrong error handling
- edge case fix
- broken test caused by small code issue

### B. Small additions
Examples:
- add a guard clause
- add a small API field mapping
- add one config-driven behavior
- add tests for an existing behavior path

### C. Small refactors
Examples:
- simplify a function
- extract small helper
- remove duplication in a narrow area
- improve readability without changing behavior

### D. Test work tied to the above
Examples:
- regression tests
- missing unit tests for touched behavior
- smoke tests for bounded change

---

# 5. Explicitly out of scope for v1

These should be rejected or escalated.

## Not supported
- database migrations
- infra or CI/CD changes
- cross-repo changes
- broad refactors
- large feature work
- security-sensitive auth changes
- payment-critical logic unless explicitly approved
- dependency upgrades with broad impact
- ambiguous product tickets without testable acceptance criteria
- tasks requiring high-level product/design judgment

## Grug rule
If the task cannot be explained as a **small bounded code change**, it is probably out of scope for v1.

---

# 6. Fully automatic spec generation

## Decision
Spec generation is fully automatic in v1.

## Why
You already chose this, and it is the right call for speed.

## Constraint
Because spec generation is automatic, Villager must be strict about refusing bad inputs.

If the system cannot produce a safe, bounded `ExecutionSpec`, it should:
- stop
- explain why
- escalate instead of guessing

## Rule
Automatic does not mean permissive.
It means:
- generate spec automatically
- reject unclear work automatically

---

# 7. What counts as “draftable”

A run is good enough for a draft PR when:

## Required
- the task is in scope
- a bounded `ExecutionSpec` exists
- changes are limited and understandable
- required deterministic checks ran
- acceptance criteria appear covered
- risks and warnings are explicit
- artifacts/logs are preserved

## Not required
- perfect solution
- merge-ready confidence in every case
- no warnings at all

## Important distinction
Draftable means:
**worth a human reviewer's time**

It does not mean:
**safe to merge without thought**

---

# 8. Success criteria for v1

Villager v1 is successful if it can do this reliably:

1. pick up a tagged JIRA task
2. classify whether the task is supported
3. generate a bounded execution spec automatically
4. execute in a sandbox
5. validate with repo-aware checks
6. produce a draft PR for supported small tasks

## Operational success metric ideas

### Quality
- % of runs that produce a reviewable draft PR
- % of draft PRs accepted by humans with minor edits only
- % of runs correctly rejected as out of scope

### Reliability
- sandbox success rate
- validation completion rate
- retry recovery rate

### Trust
- % of PRs where reviewers say “this saved time”
- % of PRs with accurate acceptance criteria coverage
- % of runs escalated appropriately instead of guessing

---

# 9. Trust model

Villager is only useful if humans can trust its output enough to review quickly.

## Trust comes from
- bounded scope
- explicit spec
- deterministic validation
- visible risk reporting
- preserved artifacts
- predictable refusal behavior

## Trust does not come from
- long reasoning traces
- agent confidence language
- fancy autonomy claims

## Product principle
The product is not “AI that writes code.”
The product is:

**small software work packaged with enough evidence that a reviewer can move fast**

---

# 10. Product boundaries

## Villager owns
- task intake
- task normalization
- spec generation
- sandboxed execution
- validation flow
- retry loop
- PR draft packaging

## Humans own
- review
- merge
- ambiguous business decisions
- sensitive approvals
- scope expansion

This boundary is important.
Do not pretend autonomy where it should not exist.

---

# 11. First implementation shape

## Recommended implementation
Start as:
- one app
- modular internals
- one queue or trigger path
- one persistence layer
- one sandbox manager

## Why
This is simpler to build, easier to debug, and much easier to change.

## Do not start with
- microservices
- multiple specialist agents
- distributed event choreography
- heavy workflow engines

Grug says:
**first make one boring path work.**

---

# 12. First rollout plan

## Stage 1
One repo, one task family, one operator.

## Stage 2
Two or three repos with different repo profiles.

## Stage 3
Introduce stricter policy rules and better review quality.

## Stage 4
Only after reliability exists, consider:
- separate reviewer agent
- richer retrieval/examples
- more task types

---

# 13. Product filters for every incoming ticket

Before a run starts, Villager should ask:

1. Is this a small bounded change?
2. Is the target repo known and profiled?
3. Are acceptance criteria concrete enough to validate?
4. Can this be tested safely in a sandbox?
5. Does this avoid forbidden high-risk areas?

If any answer is no, do not push through.
Reject or escalate.

---

# 14. Opinionated v1 rule set

## Rule 1
Prefer refusing a bad task over pretending competence.

## Rule 2
Prefer a small successful change over a bigger clever one.

## Rule 3
Prefer deterministic checks over subjective review.

## Rule 4
Prefer one executor plus strong harness over multi-agent complexity.

## Rule 5
Prefer draft PRs over autonomous merge behavior.

## Rule 6
Prefer legible system boundaries over impressive demos.

---

# 15. What this means for the next docs

Now that scope is narrowed, the next high-value docs are:

1. `execution-spec-generation.md`
2. `repo-profile-spec.md`
3. `validation-strategy.md`
4. `sandbox-design.md`
5. `interfaces-and-services.md`

That is the right order because:
- first define how work gets bounded
- then define personalization
- then define trust checks
- then define execution environment
- then define module/service shape

---

# 16. Grug conclusion

Villager v1 should do one thing well:

**take a small JIRA task, make a small safe code change, prove what happened, and hand a human a draft PR.**

That is enough.
Anything bigger is backlog.
