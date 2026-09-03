---
name: dev-loop
description: "Use as the controlling workflow for any repository implementation or content change. Coordinates acceptance criteria, actual target resolution, task branch/worktree isolation, atomic verified commits, staged-diff review, commit message generation, real usage, regression review, and final integration handoff. Trigger on implement, fix, refactor, add feature, change, make ready, or ship requests. Do not use for pure Q&A, read-only investigation, or review-only work. 中文触发：实现、修复、重构、加功能、改一下、做完、可交付。"
---

# Dev Loop

Use this skill as the controlling delivery workflow. Repository instructions
and explicit user requirements remain authoritative; the linked skills own
their specialized mechanics.

## Linked skill responsibilities

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
- Identify affected repositories and the actual integration target for each
  one. Never infer `main`, and do not assume several repositories share a
  target.
- Record material constraints, explicit non-goals, and uncertain premises.
  Test the cheapest premise most likely to invalidate the direction.

### 2. Preserve the baseline and isolate the task

- Capture the task-start branch, status, relevant diffs, and untracked files.
  Treat every pre-existing change as user-owned baseline.
- Use `$git-workflow-and-versioning` to create or reuse one short-lived task
  branch per affected repository from the verified target.
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
- If a changed artifact is not in a Git repository, state that branch and
  commit checkpoints are unavailable and preserve an explicit before/after
  comparison instead.

### 3. Define ordered atomic increments

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
- Order increments so each committed state remains buildable and includes the
  tests and generated artifacts required for that state.
- Do not create WIP, placeholder, knowingly failing, or cleanup-only commits to
  empty the worktree.

### 4. Complete and review one increment at a time

For each increment, finish this loop before starting the next:

1. Implement the smallest acceptance-complete slice using existing repository
   patterns where possible.
2. Run the narrowest relevant automated check. Add or broaden tests when the
   risk surface or repository contract requires it.
3. Exercise the changed path as a real caller or user when applicable.
4. Review the increment for scope drift, hidden coupling, generated artifacts,
   security, accessibility, and regressions directly caused by the change.
5. Stage only the exact files or hunks belonging to this increment. Never use a
   broad staging command when unrelated changes may be present.
6. Inspect status and the complete staged diff. Confirm that it is atomic,
   contains no user baseline or secret, and matches the increment's evidence.
7. For a planned feature commit, invoke `$commit-generate` against the staged
   diff, then commit with that reviewed message unless the user opted out of
   commits or the environment is not a Git repository. For review remediation,
   use `$git-workflow-and-versioning`'s `git commit --fixup=<feature-commit>`
   contract; do not invent another independent message.
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
    permitted next commit is an acceptance-complete remediation commit, which
    repeats this entire per-commit loop with its own fresh reviewer. Start the
    next planned increment only after the current implementation/remediation
    chain has no unresolved findings and its final review is accepted.
11. If this is a feature/remediation group, converge it before the next planned
    feature. Require private-history authority, run autosquash from the feature
    parent, prove the final tree equals the last reviewed tree, and preserve the
    original receipts. For a Plane-managed task, record the original-to-final
    mapping with `phase-record-history-rewrite` before continuing. A tree change
    makes the squashed result a new commit requiring verification and OCR.

When a check fails, stop this increment. Record the earliest actionable error,
the demonstrated cause or labeled hypothesis, cleanup result, and next changed
diagnostic variable. Do not rerun an unchanged failing chain. Continue the
changed diagnostic and corrective work in the same turn; only dependent planned
increments remain blocked.

If the formal OCR verdict is incomplete or failed, stop at the review checkpoint,
preserve its native receipt/log, and report `not complete`; do not silently wait,
create a later commit, or claim acceptance.
This checkpoint ends the active turn only when a changed packet scope or
invocation cannot make meaningful progress without a waiver, user input, or an
external-state change. Otherwise diagnose the timeout and continue within the
same turn under `$open-code-review`'s retry rules.

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

- the target branch and final head
- the logical commits or, outside Git, the isolated before/after delta
- targeted and final verification actually run
- real usage performed or why it was not applicable
- adversarial findings and their dispositions when review applies
- external actions performed and any intentionally unperformed handoff

If a required gate is missing, say the work is not complete and name the first
unpassed checkpoint. Never convert skipped verification into evidence.
