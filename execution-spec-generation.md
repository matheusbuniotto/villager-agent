# Villager — Execution Spec Generation

## One-sentence definition

Execution Spec Generation is the process that turns a raw JIRA ticket plus repo context into a bounded, testable work order that the executor can safely attempt.

---

# 1. Why this matters

This is one of the most important parts of Villager.

If this step is weak, everything after it gets weaker:
- execution becomes noisy
- validation becomes less meaningful
- retries become random
- draft PRs become less trustworthy

The executor should not start with a vague ticket.
It should start with a **bounded contract**.

---

# 2. Inputs to spec generation

Execution spec generation should use only a small set of inputs.

## Required inputs
- raw JIRA issue
- normalized `TaskPacket`
- `RepoProfile`

## Optional supporting inputs
- linked issue comments
- repo file tree summary
- selected examples of good past PRs
- simple codebase hints (entrypoints, test locations, package layout)

## Grug rule
Do not require fancy retrieval to make v1 work.
Start with the smallest useful context set.

---

# 3. Output of spec generation

The output is an `ExecutionSpec`.

This should define:
- the problem statement
- scope in
- scope out
- likely target areas
- acceptance criteria
- validation steps
- stop conditions
- escalation conditions
- required artifacts

If the system cannot generate this clearly, it should not proceed.

---

# 4. Design goal

The goal is **not** to perfectly understand the ticket.
The goal is to determine whether the task can be turned into:

**small + bounded + testable + repo-compatible work**

If yes, produce a spec.
If no, reject or escalate.

---

# 5. Recommended generation pipeline

Use a simple pipeline.

```text
Raw JIRA Issue
   -> Task Normalization
   -> Scope Classification
   -> Repo Compatibility Check
   -> Ambiguity Detection
   -> Risk Check
   -> ExecutionSpec Draft
   -> Spec Quality Gate
   -> EXECUTE or ESCALATE
```

This is the right shape for v1.

---

# 6. Step-by-step pipeline

## Step 1: Normalize the JIRA issue

### Goal
Convert raw issue content into a stable `TaskPacket`.

### Extract
- issue key
- title
- description
- labels/tags
- acceptance criteria if present
- linked repo
- comments that clarify behavior
- priority

### Output
A `TaskPacket` with normalized language and missing-data flags.

### Example normalization questions
- What is the requested behavior change?
- What repo does this belong to?
- Is the task about bug fix, addition, refactor, or something else?
- Are acceptance criteria explicit or implied?

---

## Step 2: Classify task type

### Goal
Decide whether the task matches supported v1 categories.

### Allowed classes
- small bug fix
- small addition
- small refactor
- test work attached to those

### Rejected classes
- migration
- infra change
- broad refactor
- cross-repo change
- security-sensitive high-risk change
- large feature work

### Important
This classification should happen before spec drafting gets too deep.

If the task is out of scope, stop early.

---

## Step 3: Check repo compatibility

### Goal
Confirm the repo is known and can support execution.

### Check
- does a `RepoProfile` exist?
- are required commands defined?
- are known forbidden/sensitive rules present?
- is this repo supported in v1?

### If no
Stop and escalate.

No repo profile means no safe personalization.

---

## Step 4: Detect ambiguity

### Goal
Decide whether the ticket is specific enough to become a bounded work order.

### Common ambiguity signals
- vague verbs like “improve,” “clean up,” “fix this flow”
- missing user-visible expected behavior
- no testable acceptance criteria
- unclear target repo or module
- multiple plausible implementations with different business outcomes
- ticket implies product judgment instead of engineering execution

### Rule
Ambiguity is not a prompt problem.
It is a routing problem.

If ambiguity blocks validation or scope definition, do not proceed.

---

## Step 5: Run risk check

### Goal
Decide whether the task is safe enough for autonomous execution in v1.

### Risk signals
- touches sensitive paths from `RepoProfile`
- likely requires migration
- likely requires dependency changes
- likely spans too many files
- likely changes shared behavior with unclear blast radius
- involves payment/auth/infra-sensitive logic

### Rule
High risk does not mean impossible forever.
It means: not for autonomous v1 by default.

---

## Step 6: Draft the `ExecutionSpec`

### Goal
Generate a bounded contract for the executor.

### The draft should include
- problem statement
- scope in
- scope out
- target areas
- acceptance criteria
- validation steps
- stop conditions
- escalation conditions
- required artifacts

### Important constraint
Do not just paraphrase the JIRA ticket.
The spec must make execution safer and narrower.

---

## Step 7: Run spec quality gate

### Goal
Check whether the spec is good enough to execute.

### Minimum quality bar
The spec must answer clearly:
1. what exact problem is being solved?
2. what should not be changed?
3. how will success be validated?
4. when should the run stop instead of guessing?

### If any answer is weak
Do not execute.
Escalate.

---

# 7. Scope classification model

Keep this simple in v1.

## Supported examples

### Small bug fix
- invalid input handling
- incorrect conditional behavior
- wrong status code
- missing edge-case guard

### Small addition
- extra field mapping
- additional validation rule
- small config-driven behavior
- small helper test

### Small refactor
- simplify one function
- extract local helper
- reduce duplication in one module
- rename for clarity within a bounded area

## Unsupported examples
- re-architect service layer
- migrate framework version
- move logic across services
- redesign auth flow
- improve system performance broadly
- “clean up the codebase”

---

# 8. Ambiguity detection rules

This deserves explicit rules.

## A task is too ambiguous if:
- expected behavior cannot be stated in one sentence
- there is no obvious acceptance test
- there is no clear repo or code area
- “done” depends on subjective product judgment
- the ticket implies multiple tasks hidden inside one

## A task is acceptable if:
- expected behavior can be stated clearly
- likely code areas are narrow
- validation path is known
- out-of-scope boundaries can be written down

## Example

### Too vague
“Improve coupon validation.”

### Good enough
“Reject empty coupon codes at API validation time and return HTTP 400 with a clear error message.”

---

# 9. Risk scoring approach

You do not need a complicated model in v1.

Use simple rule-based scoring.

## Example signals
- sensitive path touched or likely touched = +3
- migration likely = +3
- dependency change likely = +2
- more than 5 files likely = +2
- shared module blast radius unclear = +2
- acceptance criteria weak = +2

## Suggested routing
- `0-2` = low risk
- `3-4` = medium risk, proceed with warnings or tighter controls
- `5+` = escalate by default

Keep this simple and adjustable.

---

# 10. What the spec must contain

A valid `ExecutionSpec` should contain at least:

## A. Problem statement
One sentence. Clear and testable.

## B. Scope in
What changes are allowed.

## C. Scope out
What must not be changed.

## D. Target areas
Likely files/modules/directories to inspect.

## E. Acceptance criteria
Concrete expected outcomes.

## F. Validation steps
Commands/checks to run.

## G. Stop conditions
When the executor should stop immediately.

## H. Escalation conditions
When the harness should route to human or fail closed.

## I. Required artifacts
What evidence must be returned.

If one of these is missing, the spec is weak.

---

# 11. Examples

## Example 1 — Good task

### Raw ticket
“Empty coupon code currently produces a server-side error. Update validation so empty strings are rejected with a clear 400 response. Add regression test.”

### Classification
- type: small bug fix
- scope: supported
- ambiguity: low
- risk: low

### Good spec result
- problem statement is clear
- target area likely narrow
- validation path exists
- out-of-scope can be written

Proceed.

---

## Example 2 — Reject task

### Raw ticket
“Improve checkout flow reliability and clean up coupon handling.”

### Problem
This is likely multiple tasks and not bounded.

### Why reject
- vague objective
- unclear acceptance criteria
- likely broad scope
- likely multiple modules/services

Escalate instead of guessing.

---

## Example 3 — Escalate for risk

### Raw ticket
“Add missing validation in payment authorization path.”

### Problem
Maybe small, but the path is payment-critical.

### Why escalate
Even if technically bounded, risk threshold is too high for autonomous v1 by default.

---

# 12. Spec quality gate checklist

Before execution starts, the harness should verify:

- [ ] task type is supported
- [ ] repo profile exists
- [ ] problem statement is clear
- [ ] scope in is explicit
- [ ] scope out is explicit
- [ ] acceptance criteria are testable
- [ ] validation steps are known
- [ ] stop conditions are defined
- [ ] escalation conditions are defined
- [ ] risk score is acceptable

If any critical item fails, stop.

---

# 13. Recommended implementation approach

For v1, keep this simple.

## Suggested architecture for this part
Use one `SpecBuilder` module with 4 internal stages:

1. `normalize_task()`
2. `classify_scope()`
3. `assess_ambiguity_and_risk()`
4. `build_execution_spec()`

Then run one final validator:

5. `quality_gate_spec()`

That is enough.

## Grug rule
No complex planning graphs.
No multi-agent debate.
One boring pipeline.

---

# 14. Failure behavior

When spec generation fails, the system should fail clearly.

## Good failure output should say
- why the task is unsupported
- whether the issue is scope, ambiguity, repo support, or risk
- what a human would need to clarify

## Bad failure output
- “Unable to proceed” with no reason
- vague confidence language
- pretending the ticket is clear when it is not

---

# 15. Relationship to the rest of Villager

Spec generation connects to everything else.

```text
JIRA Issue
  -> TaskPacket
  -> ExecutionSpec
  -> Sandbox Execution
  -> Validation
  -> ReviewDecision
  -> Draft PR
```

If `ExecutionSpec` is good, the rest of the chain gets easier.
If `ExecutionSpec` is bad, the rest becomes damage control.

---

# 16. Opinionated recommendation

Villager should be conservative here.

## Prefer this
- smaller specs
- more refusals
- tighter boundaries
- explicit stop conditions

## Avoid this
- stretching vague tickets into action
- broad inferred scope
- pretending uncertainty is okay
- starting execution just to “see what happens”

For v1:
**conservative spec generation beats clever speculation**

---

# 17. Next doc

Best next document:

**`repo-profile-spec.md`**

Why:
Once spec generation is defined, the next most important thing is the personalization contract that shapes execution and validation per repo/team.
