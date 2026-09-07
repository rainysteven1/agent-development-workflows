# Autonomous Engineering Harness Contract

This contract controls explicit long-horizon work. It separates progress,
quality evidence, reviewer feedback, infrastructure health, and human authority
so one signal cannot accidentally control the whole run.

## Authority boundary

The user grants standing authority for local, reversible work inside the fixed
objective, repositories, acceptance checks, and trust boundaries. Reuse an
approval only when its key matches `(action class, scope, target)`; never infer
approval for a broader target or external effect.

Interrupt the user only when the next required edge needs at least one of:

- a product decision or acceptance change;
- a scope, architecture ownership, or trust-boundary change;
- new credentials, authorization, or access controlled by another party;
- an external, destructive, irreversible, published, deployed, pushed, merged,
  or safety-critical physical action not already authorized; or
- unavailable hardware/human judgment when no independent safe work remains.

Do not interrupt for a test failure, reviewer finding, retry count, commit or
Phase boundary, hook-compatible local Git choice, timeout, rate limit, provider
failure, or optional hardware while a safe in-scope path remains.

## Current delivery boundary and complexity budget

Before implementation, freeze one short scope record in the existing task ledger:

- `must_now`: current observable outcomes and their acceptance IDs;
- `not_now`: later-Phase work and optional hardening, with reopen conditions;
- `evidence`: distinguish observed failures, source-proven reachable defects,
  and unverified hypotheses;
- `budget`: named owning modules and allowed additions to persistent state,
  retry layers, abstractions/dependencies, and test scope; and
- `finish`: the minimum checks and required review coverage that close this slice.

Derive this record from the authorized task and active Phase. A later Phase's
checklist provides context, not current implementation obligations. Pull a later
item forward only when a concrete dependency makes current acceptance impossible
without it; record the dependency and reconcile planning before changing scope.
Do not silently defer an active acceptance requirement to fit the budget.

Set concrete limits for relevant dimensions before editing, for example: reuse
the existing job state and retry owner, add no dependency or second queue, and
verify at the component seam. Omit irrelevant dimensions. Zero new mechanisms is
the default unless the current contract requires them; name each necessary
addition and its purpose. This is a design budget, not a universal line-count,
test-count, or one-retry rule.

Before adding a guard, fallback, retry, state, or fault-injection scenario, map it
to a current requirement or demonstrated reachable defect and its cheapest check.
Production incidents are not required: source-level causal proof or a deterministic
test using a real caller's allowed states is valid evidence. Arbitrary fake-only
states, imagined future consumers, and unsupported SDK behavior are hypotheses;
investigate cheaply when material, otherwise defer with a reopen condition.

If implementation or review remediation would exceed the budget, pause that
addition and re-examine the owning layer and whole root cause. Prefer replacing
the flawed mechanism over stacking another one. Revise the budget only with new
evidence and an explanation of why the simpler design cannot meet acceptance;
renaming or splitting commits does not reset it. Continue local redesign within
existing authority; ask only at the authority boundary above.

Once the recorded checks and required reviews pass, stop adding tests or
hardening. Missing receipts require evidence reconciliation, not new behavior or
repeated accepted reviews. Preserve unresolved required gates as incomplete.

## Run state

Keep exactly one current state in the durable task ledger:

| State | Meaning | Required next action |
|---|---|---|
| `working` | The next acceptance edge is known and healthy. | Execute the smallest complete increment. |
| `recovering` | An edge failed and a changed diagnostic variable exists. | Record the failure signature, change one variable, and retry the edge. |
| `degraded` | Supporting infrastructure such as a reviewer/provider is unavailable. | Preserve native evidence, block claims that require it, and continue only independent local work. |
| `waiting_infrastructure` | Required supporting infrastructure is unavailable and no independent safe edge remains. | Checkpoint the run and report the external recovery trigger without requesting permission. |
| `waiting_external` | A required edge crosses the authority boundary above. | Pause that edge, finish independent work, then issue one batched interrupt. |
| `done` | Every acceptance check and required gate passes at the claimed revisions. | Hand off the verified result. |

A failed edge blocks its dependants, not the whole run. A Phase may advance only
when its own authority says it is complete; independent preparation does not
become false Phase progress.

## Control loop

For each increment:

1. Select one acceptance edge and the cheapest falsifier.
2. Capture the exact target, current revision, baseline, and expected
   observation.
3. Act once through maintained repository automation.
4. Classify the observation as `passed`, `correctable_failure`,
   `infrastructure_unavailable`, or `authority_required`.
5. Update the ledger and state before choosing another action.

On `correctable_failure`, preserve this failure signature:

```text
(acceptance edge, action/tool, exact target, normalized arguments,
 earliest actionable error)
```

Ignore timestamps, request IDs, token counts, and other incidental values when
comparing signatures. Record the observed source revision beside the signature
for traceability, but do not use it for equivalence: a remediation commit must
not reset the same-failure detector by itself. Never repeat an identical failing
action unchanged. A successful falsifier or a new causal observation resets the
consecutive-failure counter for that edge.

Persist a `strategy_id`, current and previous normalized signatures,
`consecutive_equivalent_failures`, and `nudge_emitted`. Context compaction,
process restart, or a fresh agent session restores these values; it never resets
the detector. Start a new strategy ID only after root-cause/interface analysis
produces a genuinely different causal approach.

At the second consecutive equivalent failure, emit one internal nudge: restate
the earliest error and require a changed diagnostic or design variable. If the
next attempt produces the same equivalent failure with no new causal evidence,
mark the strategy `no_progress`, stop that strategy, and return to root-cause or
interface design. Do not ask the user merely because the counter fired. Move to
`waiting_external` only if every new safe strategy requires the authority
boundary.

Global step, cost, or wall-time budgets are safety controls and evidence fields,
not permission prompts. When one is reached, checkpoint state and resume in a
fresh context if the product supports it; do not silently lower the acceptance
bar.

## Reviewer harness

Deterministic checks run before review. Review is an adversarial sensor, not the
completion oracle and not an optimizer that must reach zero comments.

Give each reviewer one immutable commit, the frozen scope record and budget,
direct consumers, trust boundaries, and actual verification. Require findings to
identify a current requirement or direct regression, reachable trigger, evidence
class, and cheapest falsifier. Optional improvements remain non-blocking; budget
pressure never dismisses a demonstrated current defect. Triage the complete
finding set before editing. Normalize every finding to this identity:

```text
(acceptance check, path/symbol, concrete failure mechanism)
```

Line movement, severity wording, reviewer prose, and narrower timing windows do
not create a new finding identity. Persist each finding as `open`, `fixed`,
`dismissed_duplicate`, `dismissed_out_of_scope`, or `dismissed_speculative`,
plus its evidence and resolving revision when applicable.

A finding is `open` only when all are present:

- a current caller or accepted requirement reaches the path;
- a concrete input, state, or interleaving triggers it;
- an observable acceptance or direct-effect violation results; and
- a cheapest falsifier can confirm or reject it.

Missing proof makes the finding speculative until the stated reopen condition
occurs. Reviewer severity never expands scope.

Group all open findings by root cause before changing code. Prefer one coherent
remediation that fixes the shared cause and its focused tests; do not create one
patch per comment. Review the remediation commit once. Another remediation is
allowed only for a newly demonstrated mechanism or a regression introduced by
the prior fix. A rephrased, duplicated, hypothetical, or already-fixed finding
is dispositioned without code or another loop.

Converge when deterministic acceptance checks pass and the finding ledger has no
open evidence-backed blocker. Do not continue merely to obtain a zero-finding
review.

If formal review infrastructure fails, retry/resume only as its own documented
contract allows. After it is unavailable, preserve the manifest and run one
independent read-only fallback review of the same immutable commit. Enter
`degraded`: the fallback does not become a receipt and cannot support formal
completion, but independent local work continues. A provider/tool failure never
creates a code requirement. When no independent safe work remains, transition to
`waiting_infrastructure`, checkpoint the exact failed service and immutable work,
and state the recovery signal that permits resume; do not ask the user to approve
an unavailable provider.

## Durable checkpoint

Keep enough state to resume without replaying chat history:

- objective, fixed acceptance checks, and the current scope record including
  non-goals, evidence classes, complexity budget, and justified budget revisions;
- repository/worktree, target, current revision, and dirty state;
- current harness state and current acceptance edge;
- last action, exact observation, changed variable, strategy ID, current and
  previous normalized failure signatures, consecutive-equivalent count, and
  whether the no-progress nudge was emitted;
- open finding identities and dispositions;
- verification and review evidence bound to immutable revisions;
- external gates and reusable approval keys; and
- next safe action.

Commit complete increments and leave the worktree explainable. Do not use the
ledger as a second product specification or copy secrets into it.

## Behavior matrix

Use these cases when changing the harness:

| Scenario | Decision |
|---|---|
| Later Phase lists restart/scale hardening absent from current acceptance | Keep it in `not_now` unless a concrete current dependency is demonstrated. |
| Fake injects a state no current caller or SDK contract permits | Classify as a hypothesis; do not add production defenses without reachability evidence. |
| Source proves a current cancellation race without a production incident | Treat it as a real defect; verify at the smallest stable seam. |
| Remediation proposes a second retry owner beyond the recorded budget | Pause the addition, redesign at the owner, and justify any evidence-driven budget revision. |
| Checks and reviews pass but a Plane receipt is missing | Reconcile existing evidence; do not expand implementation or repeat accepted review. |
| Third local remediation fixes a newly proven in-scope mechanism | Continue; the number is not an approval boundary. |
| Reviewer repeats the same concern with different prose or line | Dismiss by finding identity; do not edit. |
| Reviewer invents a future caller or stronger threat model | Dismiss out of scope with a reopen condition. |
| Same command and normalized arguments return the same error | Do not rerun unchanged; change one diagnostic variable. |
| Two equivalent failures trigger the nudge and the changed strategy fails equivalently | Stop that strategy and return to diagnosis/design. |
| Formal reviewer fails but tests and independent work remain | Enter `degraded`; preserve evidence and continue independent work. |
| Formal reviewer fails and no independent work remains | Enter `waiting_infrastructure`; checkpoint and report the recovery trigger without asking permission. |
| Repository hook rejects `fixup!` but accepts Conventional Commits | Keep a normal reviewed remediation chain; do not bypass or ask. |
| Production deploy, push, merge, credential, deletion, or physical safety action is required | Reuse matching explicit approval or enter `waiting_external`. |
| Hardware is unavailable but equivalent local acceptance is explicitly allowed | Complete the equivalent evidence and retain HIL as a declared boundary. |
| Every remaining edge needs missing authority or hardware | Issue one batched interrupt with the exact decision required. |
| Every remaining edge needs unavailable non-user infrastructure | Pause as `waiting_infrastructure`; do not turn outage into an approval question. |

## Design basis

- Anthropic's autonomous-coding quickstart uses a durable feature list, progress
  file, pre-work regression, one feature per increment, and clean commits.
- OpenHands compares normalized action/observation content, nudges a repeated
  action-error streak once, and detects continued semantic repetition rather
  than counting every changed attempt as stuck.
- mini-SWE-agent separates step, cost, wall-time, and consecutive format-error
  limits, resets the consecutive counter after a clean step, and saves the
  trajectory in `finally`.
- OpenAI Agents SDK persists `RunState`, keys approvals to tool-call identity,
  supports sticky decisions inside a run, and permits programmatic approvals for
  trusted tool classes.
- Aider separates auto-lint, auto-test, auto-commit, hook verification, and dry
  run controls instead of coupling them into one success signal.
- PR-Agent persists finding fingerprints/state, supports incremental review,
  limits noisy output, and distinguishes incomplete coverage; reviewdog filters
  diagnostics against the changed diff.

These sources inform the control shape. Repository instructions, user authority,
and deterministic local evidence remain the operative facts.
