---
name: dev-loop
description: "Use as the controlling workflow for any repository implementation or content change. Coordinates acceptance criteria, actual target resolution, task branch/worktree isolation, atomic verified commits, staged-diff review, commit message generation, real usage, regression review, and final integration handoff. Trigger on implement, fix, refactor, add feature, change, make ready, or ship requests. Do not use for pure Q&A, read-only investigation, or review-only work. 中文触发：实现、修复、重构、加功能、改一下、做完、可交付。"
---

# Dev Loop

Use this skill as the controlling delivery workflow. Repository instructions
and explicit user requirements remain authoritative; the linked skills own
their specialized mechanics.

## Linked skill responsibilities

- `$long-horizon`: when explicitly active, own run state, failure signatures,
  reviewer convergence, degraded-mode continuation, and human interrupts through
  its single harness contract.
- `$git-workflow-and-versioning`: resolve the real integration target, define
  atomic increments, stage exact changes, inspect history, and maintain branch
  and commit integrity.
- `$using-git-worktrees`: decide whether existing isolation is sufficient and
  create a task worktree only when isolation is required.
- `$commit-generate`: draft a message only after one complete atomic increment
  has been staged and inspected. It does not choose commit boundaries or stage
  files.
- `$repo-evidence`: route exact, semantic, and structural repository discovery
  and return revision/freshness-bound evidence. It does not choose implementation
  scope by itself.
- `$codebase-design`: decide module responsibility, interface placement, and a
  stable testing seam when those are part of the problem.
- `$diagnosing-bugs`: prove the root cause of a hard or uncertain failure before
  any corrective implementation. A diagnosis-only request stops before edits.
- `$tdd`: own a risk-driven red-green-refactor loop for observable behavior at
  an established seam; it does not control the broader delivery sequence.
- `$lean-delivery`: select the smallest acceptance-complete implementation after
  the required evidence, design, and feedback loop are established.
- `$writing-for-agents`: design routing, hierarchy, and checkable completion for
  AGENTS, Skills, and other agent-facing instructions.
- `$stop-slop`: polish human-facing technical prose within its declared scope
  after facts and constraints are correct. It does not edit agent instructions,
  API/schema reference, legal text, code comments, or commits.
- `$existing-project`: perform first-repository bootstrap or reuse a verified
  project map in resume/delta mode. A new worktree does not trigger full
  repository recovery.
- `$finishing-a-development-branch`: verify the finished branch and perform the
  user-authorized integration handoff.

Read a linked skill completely before entering the stage it owns. Do not copy
its detailed procedure into this skill.

## Delivery pipeline

Stopping an increment or downstream work never requires ending the active turn.
Continue diagnosis, remediation, verification, review, and evidence recording in
the same turn whenever meaningful safe in-scope progress remains. A failed check,
review finding, incomplete commit, or Phase boundary is not a terminal condition.

### 1. Fix the target and acceptance contract

- Restate the user-visible outcome and the narrowest observable checks that
  prove it.
- Identify affected repositories. For committed delivery or requested integration,
  resolve the actual integration target for each one. Never infer `main`, and do
  not assume several repositories share a target.
- Record material constraints, explicit non-goals, and uncertain premises.
  Test the cheapest premise most likely to invalidate the direction.
- For explicit autonomous work, use `$long-horizon`'s current delivery boundary
  and complexity budget as the scope record shared by implementation and review.
  Preserve it across increments and compaction; later Phase checklists do not
  implicitly expand the current slice.
- Classify the change before selecting optional workflows. A small reversible
  change may proceed from a fixed contract; a material unsettled design uses
  `$create-plan`; a Plane-managed design follows the verified Plane authority;
  and a high-risk change explicitly freezes trust boundaries, recovery, and
  rollback evidence.

Choose the delivery mode from the user's request and environment:

- **Committed delivery:** use the per-commit pipeline when the task permits commits in Git.
- **Verified local delta:** when the user requests no commits or the artifact is outside Git,
  deliver the verified changes without staging, committing, or inventing a commit receipt.
  Preserve the starting bytes and a focused before/after diff; record the changed-file content
  hashes alongside verification so later edits invalidate the affected evidence. A read-only
  request stays outside this implementation workflow.

An explicitly required commit, integration, or Plane gate remains pending if the user defers its
prerequisite. Report the completed local scope separately; do not claim that downstream gate passed.

### 2. Preserve the baseline and isolate the task

Git branch and worktree steps apply only inside Git. Verified-local mode still preserves and
isolates the user's baseline, but does not require an integration target unless integration is
part of the requested scope; use the verified task-start revision for local isolation otherwise.

- Capture the task-start branch, status, relevant diffs, and untracked files.
  Treat every pre-existing change as user-owned baseline.
- For committed delivery, use `$git-workflow-and-versioning` to create or reuse one
  short-lived task branch per affected repository from the verified target. In
  verified-local mode, retain valid task isolation or isolate from the recorded
  starting revision without staging or committing the user's baseline.
- Use `$using-git-worktrees` when the current checkout is dirty, contains
  unrelated work, is on another task branch, or otherwise cannot isolate the
  requested range. Reuse valid existing isolation instead of nesting it.
- Inventory ignored inputs and environment prerequisites before running setup,
  tests, builds, or external mutations from a new worktree. Never copy secrets
  into it.
- For an existing repository with a managed canonical worktree, invoke
  `$existing-project` in resume/delta mode and `$repo-evidence` with the recorded
  canonical baseline. Verify the shared Git common directory and map revision.
  Inherit only a private Graft snapshot and refresh it in the task worktree;
  query canonical Zvec-Grep for stable semantic candidates and never copy its
  root-bound index. Full recovery is reserved for the escalation conditions in
  `$existing-project`.
- When managed index lifecycle configuration exists, read its revision-keyed
  status after worktree creation. The owned post-checkout hook normally prepares
  the private Graft snapshot; run `index_lifecycle.py prepare-worktree --apply`
  whenever task status is absent or anything other than `ready`, then re-read
  it. Never treat hook exit alone as readiness evidence.
- If a changed artifact is not in a Git repository, state that branch and
  commit checkpoints are unavailable and preserve an explicit before/after
  comparison instead.

### 3. Define ordered atomic increments

In verified-local mode, use independently verifiable edit slices instead of planned commits.
Commit identity, commit ordering, and post-commit index rules apply to committed delivery only.

- Trace the affected flow, direct consumers, and maintained artifacts before
  choosing increments.
- For cross-module refactors, deletion work, or other graph-sensitive changes,
  invoke `$repo-evidence`. Record repository root, full `HEAD`, dirty state,
  tool/version, index readiness and coverage, freshness result, and blind spots.
  Semantic and structural results are candidates, not proof of no consumers.
  Confirm scope with source, exact search, compiler/type checks, tests,
  generated/configuration entrypoints, and known cross-repository consumers.
- Development-time Graft evidence may describe uncommitted working-tree bytes.
  Before it supports final immutable scope, require a clean worktree at the
  claimed `HEAD` and the installed tool's maintained freshness check. An
  automatic query refresh or post-checkout invalidation hook is not final
  evidence by itself.
- Give every increment one independently reviewable reason to change and its
  own acceptance check.
- Preserve stable `AC-*` identifiers from an approved delivery brief or Plane
  plan and map each required criterion to its planned test or real-usage
  mechanism. Do not let a green suite substitute for an unmapped requirement.
- Before the first review, freeze the feature's acceptance checks, direct
  consumers, and trust boundaries. When `$long-horizon` is active, load and use
  its harness contract before the first task action; do not duplicate its retry,
  reviewer, progress, or escalation rules in this workflow.
- Order increments so each committed state remains buildable and includes the
  tests and generated artifacts required for that state.
- Do not create WIP, placeholder, knowingly failing, or cleanup-only commits to
  empty the worktree.

### 4. Complete and review one increment at a time

For each increment, finish this loop before starting the next:

Choose the specialized path before editing. For an uncertain, intermittent,
cross-layer, performance, or repeatedly failing bug, invoke `$diagnosing-bugs`
and do not implement until its root cause is proven and a fix is authorized.
When module ownership, interface placement, or the testing seam is unclear,
invoke `$codebase-design`. When `$tdd` applies, establish and observe the red
test at that seam before production changes. These Skills feed this loop; none
replaces its Git, review, or completion gates.

In verified-local mode, perform steps 1-4 below for each slice, inspect its complete before/after
delta, and capture the verified content hashes. Skip steps 5-11 and the branch/integration stages
5-6. Complete applicable cumulative checks and real usage against the final bytes, reconcile
task-owned temporary resources, and report through the completion gate. Honor an explicitly
requested development review at this seam; do not turn it into a formal `ocr review --commit`
receipt or require a commit merely to finish the local request.

1. Implement the smallest acceptance-complete slice using existing repository
   patterns where possible.
2. Run the narrowest relevant automated check. Add or broaden tests when the
   risk surface or repository contract requires it.
3. Exercise the changed path as a real caller or user when applicable.
4. Review the increment for scope drift, hidden coupling, generated artifacts,
   security, accessibility, and regressions directly caused by the change.
   For agent-facing instructions, invoke `$writing-for-agents`; for formal
   human-facing prose within its scope, invoke `$stop-slop` after semantic
   correctness. API/schema reference and other excluded artifacts stay on the
   repository-native documentation route unless a more specific Skill applies.
   In a mixed-audience document, apply `$writing-for-agents` to agent
   instructions and restrict `$stop-slop` to explicitly human-facing sections;
   keep executable agent instructions outside that style pass.
5. Stage only the exact files or hunks belonging to this increment. Never use a
   broad staging command when unrelated changes may be present.
6. Inspect status and the complete staged diff. Confirm that it is atomic,
   contains no user baseline or secret, and matches the increment's evidence.
7. For a planned feature commit, invoke `$commit-generate` against the staged
   diff, then commit with that reviewed message unless the user opted out of
   commits or the environment is not a Git repository. For review remediation,
   use `$git-workflow-and-versioning`'s `git commit --fixup=<feature-commit>`
   contract. If a verified repository hook rejects fixup subjects, use one
   ordinary Conventional Commit remediation, retain the reviewed linear history,
   and skip autosquash; do not interrupt the user over this local mechanism.
8. Verify the commit identity and that no intended staged content was left
   behind. Record the command evidence tied to that commit. Treat any prior
   task structural index as stale; rely on a repository invalidation hook when
   one is maintained, otherwise record the invalidation explicitly. Refresh
   task-local Graft before the next graph-dependent decision and require its
   blocking build/check to succeed; do not rebuild or copy the canonical
   Zvec-Grep baseline after every task commit.
9. Invoke `$open-code-review`'s formal `ocr review --commit` verdict for exactly
   the immutable parent-to-commit range. Require native complete terminal state,
   full preview-file coverage, no failed/budget-skipped item, and dispositioned
   findings; record OCR version/provider/model/effort, rule fingerprint, session
   ID, and both SHAs. For security, concurrency, migration, or deployment-risk
   changes only, add one fresh Luna second opinion against the same packet; it is
   supplementary and never replaces the OCR verdict.
10. Disposition every finding. While this increment is not accepted, the only
    permitted next commit is an acceptance-complete remediation commit. Triage
    the complete finding set first, normalize duplicates, and group open findings
    by root cause; do not create one patch per reviewer comment. The remediation
    repeats this per-commit loop with its own fresh reviewer. Start dependent
    work only after the finding ledger has no open blocker. The sole exception
    is explicit `$long-horizon` degraded mode: a materially independent local
    increment may commit after its own deterministic checks and exact-commit
    fallback review, while every missing formal receipt remains open.
11. If every remediation in the feature group uses a `fixup!` subject, converge
    it before the next planned feature. Require private-history authority, run
    autosquash from the feature parent, prove the final tree equals the last
    reviewed tree, and preserve the original receipts. For a Plane-managed task,
    record the original-to-final mapping with `phase-record-history-rewrite`
    before continuing. A tree change makes the squashed result a new commit
    requiring verification and OCR. Preserve any group containing a
    repository-required normal remediation as reviewed linear history instead
    of rewriting it.

### Bound review convergence

`$open-code-review` owns immutable review execution and receipts. The
`$long-horizon` harness contract owns finding identity, evidence classification,
root-cause grouping, no-progress detection, and user interruption whenever that
mode is active. Deterministic acceptance checks, tests, and real usage remain the
completion oracle; reviewer severity and zero findings do not.

When a check fails, stop this increment. Record the earliest actionable error,
the demonstrated cause or labeled hypothesis, cleanup result, and next changed
diagnostic variable. Do not rerun an unchanged failing chain. Continue the
changed diagnostic and corrective work in the same turn; only dependent planned
increments remain blocked.

In ordinary mode, after three unsuccessful evidence-backed corrections for the
same failure, return to `$diagnosing-bugs` and `$codebase-design` before another
edit. In long-horizon mode, use the contract's normalized failure signature,
single nudge, and `no_progress` transition instead of counting changed attempts.

If formal OCR is incomplete or failed, preserve its native artifact and follow
`$open-code-review`. A fallback never becomes acceptance evidence. When
`$long-horizon` is active, its `degraded` state decides what independent local
work may continue and what dependent claims remain stopped.

### 5. Verify the complete branch

- Inspect the full commit sequence and diff against the verified target, not
  only the last commit.
- If completion claims depend on structural-graph evidence, refresh its
  freshness check at the final head and repeat the recorded blind-spot checks;
  a graph bound only to an earlier commit is not final evidence.
- Run the repository-required final checks, plus a realistic happy path and
  relevant edge or failure path when applicable.
- Recheck that the source revision used by every claimed result is the current
  branch head. Older CI, build, render, or runtime results are stale after a new
  commit.
- Confirm every material commit in the task range has its own complete OCR
  manifest, fresh-reviewer batches, same-session synthesis, and finding
  disposition. Do not replace this ledger with a branch-, MR-, Phase-, or
  Work-Package-wide adversarial review.
- Confirm no `fixup!` remediation commit remains in the final range. Each final
  feature commit must have either its own review marker or a validated
  history-only provenance mapping to the original reviewed feature/fixup chain.
- Treat final branch regression and cross-commit or cross-repository real usage
  as cumulative verification, not another adversarial review round. If that
  verification requires a code or documentation commit, send the new commit
  through the complete per-commit loop before continuing.

### 6. Hand off integration

- Use `$finishing-a-development-branch` after implementation, findings, and
  required checks are green.
- Include the canonical worktree and index-baseline revision in the finish
  packet when this task used managed repository evidence. After verified
  integration, refresh the existing canonical Graft/Zvec-Grep baselines once;
  never backfill a task-local Zvec-Grep index.
- For a managed repository, verify the post-merge/post-rewrite hook recorded the
  integrated target SHA as canonical `ready`. If it did not, run the maintained
  `index_lifecycle.py converge --apply` command and re-read status. The same SHA
  must return `already-ready` without rerunning Graft or Zvec-Grep.
- Before push or merge, confirm the intended target, complete commit range,
  current head SHA, clean task range, and absence of user-baseline changes.
- Push, open or update an MR, merge, publish, deploy, or clean up remote state
  only when the user has authorized that external action and its required gates
  pass.
- Treat CI as evidence only for the exact current head. Re-read the head before
  the final external mutation.

## Completion gate

Report completion only when all applicable pipeline stages passed for the final
revision. State:

- the target branch and final head for committed delivery, or starting revision when available
  and final changed-file content hashes for a verified local delta
- the logical commits for committed delivery, or the focused before/after delta
  for verified-local delivery
- targeted and final verification actually run
- real usage performed or why it was not applicable
- adversarial findings and their dispositions when review applies
- external actions performed and any intentionally unperformed handoff

If a required gate is missing, say the work is not complete and name the first
unpassed checkpoint. Git commit and integration gates are inapplicable to an exclusively
verified-local request; report that local scope as complete when its checks pass, explicitly
noting that no commit or integration occurred. Never convert skipped verification into evidence.
