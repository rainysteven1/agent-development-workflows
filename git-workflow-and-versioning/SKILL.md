---
name: git-workflow-and-versioning
description: Resolve integration targets, create task branches, define atomic commit boundaries, stage and inspect exact changes, maintain reviewable history, handle conflicts, and apply repository versioning rules. Use for any version-controlled change or release preparation. When invoked by dev-loop, this skill owns Git mechanics rather than implementation, testing, message drafting, or integration authorization.
---

# Git Workflow and Versioning

Keep every task range isolated, reviewable, buildable, and tied to the actual
integration target.

## Responsibility boundary

- `$dev-loop` controls the end-to-end delivery sequence and acceptance gates.
- `$using-git-worktrees` owns workspace isolation mechanics.
- `$commit-generate` drafts a message from an already staged atomic diff.
- `$finishing-a-development-branch` owns the authorized push, MR, merge, and
  cleanup handoff.

This skill decides Git state and commit boundaries. It does not invent test
commands, stage unrelated changes, or authorize external mutations.

## Establish the Git baseline

Before changing tracked files, record:

```bash
git status --short --branch
git remote -v
git branch -vv
git worktree list --porcelain
```

Inspect focused staged and unstaged diffs for relevant paths. Treat every
pre-existing modification and untracked file as user-owned baseline.

## Resolve the actual integration target

Determine the target independently for every affected repository. Use evidence
in this order:

1. the explicit user request, work item, or existing MR target branch
2. the closest repository instructions or maintained contribution workflow
3. the forge or remote default branch only when the task has no more specific
   integration policy or target

The remote default is evidence, not a synonym for `main`. Verify that the
resolved target is a branch ref, verify that it exists, and record its full
commit SHA before branching. A task branch's upstream, fork point, or merge
base can validate its starting revision only; none of them identifies the
branch into which the task should integrate. If two plausible target branches
remain and choosing one would change the review range, stop and ask rather than
guessing.

Do not assume repositories in one work package share a target.

## Create or reuse the task branch

- Reuse the current branch only when it is already dedicated to this task, its
  target is verified, and its range contains no unrelated work.
- Otherwise create one short-lived branch per affected repository from the
  verified target. Follow repository naming rules; absent a local rule, use a
  concise `feat/`, `fix/`, `refactor/`, `docs/`, or `chore/` prefix.
- When the checkout is dirty, carries another task, or cannot isolate the
  requested range, hand workspace creation to `$using-git-worktrees`.
- Never move, discard, stash, or commit the user's baseline merely to make room
  for the task.

## Define atomic increments

Before editing a non-trivial change, list the ordered commits. Every increment
must:

- have one independently reviewable reason to change
- leave the repository buildable under the applicable project contract
- include the tests and generated artifacts needed to keep that state valid
- exclude unrelated cleanup, formatting, dependencies, and user baseline

About 100 changed lines is a reviewability signal, about 300 may still be one
coherent increment, and a change approaching 1000 lines should be split unless
generated output or an indivisible contract makes splitting less correct.
Logical atomicity and a green state take precedence over numeric size.

Do not create partial, placeholder, knowingly failing, or WIP commits.

## Stage and commit one increment

Finish implementation and its targeted verification before staging. Then:

1. Stage only explicit paths or selected hunks for the current increment. Do
   not use `git add .` or `git add -A` when any unrelated state may exist.
2. Inspect `git status --short`, `git diff --cached --stat`,
   `git diff --cached --check`, and the complete `git diff --cached`.
3. Confirm the staged diff matches one increment, contains no user baseline or
   secret, and includes its required tests and generated artifacts.
4. Invoke `$commit-generate` using that staged diff. Review the message against
   repository conventions and the actual intent.
5. Commit without bypassing hooks. Do not amend or rewrite commits owned by the
   user unless explicitly authorized.
6. Record `git rev-parse HEAD` and verify no intended staged change remains.

If the staged diff mixes reasons to change, unstage only task-owned paths or
hunks and split it before committing. Never use a destructive reset as routine
workflow recovery.

## Inspect the complete branch

Before push, MR creation or update, review, or merge, inspect the full range
against the verified target:

```bash
git merge-base <target> HEAD
git log --oneline --decorate <target>..HEAD
git diff --stat <target>...HEAD
git diff <target>...HEAD
git status --short --branch
git rev-parse HEAD
```

Confirm every commit remains scoped and independently understandable, the
range excludes baseline changes, and verification evidence belongs to the
current head.

## Conflicts and history safety

- Resolve conflicts against the intended behavior and both sides' current
  contracts, not by choosing one side wholesale.
- Re-run checks affected by the resolution and inspect the resulting range.
- Do not force-push, rewrite shared history, delete branches, or discard a
  worktree without explicit authorization and exact target verification.
- Prefer additive follow-up commits for an already reviewed or shared branch.
  Rewrite only when the branch is proven private and the user requested clean
  history.

## Versioning and releases

Apply versioning only when the repository or current task has a consumer-facing
version contract.

- Follow the repository's version source and release tooling; do not introduce
  a parallel version file or manual process.
- Under semantic versioning, use major for incompatible released behavior,
  minor for backward-compatible capability, and patch for backward-compatible
  fixes.
- Keep the consumer-facing changelog curated by impact rather than copying the
  commit log.
- Treat tags and published artifacts as immutable. Creating or pushing a tag,
  publishing, or releasing requires explicit authorization and the applicable
  release gates.

## Completion evidence

Return the verified target and SHA, task branch and head SHA, commit list,
current status, and any versioning decision. Report an unresolved target,
mixed range, failing hook, or unsafe history operation as a blocking checkpoint
to `$dev-loop`.
