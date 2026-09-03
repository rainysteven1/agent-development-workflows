---
name: using-git-worktrees
description: Create or reuse an isolated Git worktree for a verified task branch without disturbing the user's checkout. Use when dev-loop finds a dirty baseline, unrelated work, another task branch, parallel work, or any checkout that cannot isolate the requested change. Owns workspace mechanics only; it does not choose the integration target, commit boundaries, or integration action.
---

# Using Git Worktrees

Protect the user's checkout while keeping the task branch tied to a verified
target. `$dev-loop` controls the delivery pipeline and
`$git-workflow-and-versioning` supplies the target and task branch name.

## 1. Confirm isolation is needed

Inspect the current workspace before creating anything:

```bash
git rev-parse --show-toplevel
git rev-parse --git-dir
git rev-parse --git-common-dir
git rev-parse --show-superproject-working-tree
git branch --show-current
git status --short --branch
git worktree list --porcelain
```

- A different Git directory and common directory usually means a linked
  worktree, but a submodule can produce similar evidence. Check the
  superproject result before deciding.
- Reuse an existing linked worktree only when its branch, target, ownership,
  and task scope match the current request.
- Do not create a nested worktree when the current workspace already provides
  valid task isolation.
- Use a new worktree when the current checkout is dirty with user baseline,
  contains another task, is on a protected target branch, or cannot produce a
  clean review range.

## 2. Verify inputs

Before mutation, obtain from `$git-workflow-and-versioning`:

- repository root and remote
- full target ref and target SHA
- unique task branch name
- known user-baseline paths that must remain untouched

Verify the target ref still resolves to the recorded SHA. If it moved, return
to `$dev-loop` to decide whether the task should use the new revision. Never
substitute a default branch for a missing target.

For an existing task branch, also record its current full tip SHA and prove the
recorded target SHA is its ancestor. A resumed task is expected to contain
task commits after its starting revision; do not compare its tip directly with
the original target SHA.

## 3. Choose the workspace mechanism

Use mechanisms in this order:

1. Reuse a matching existing worktree.
2. Use a host-provided native worktree facility when available.
3. Use `git worktree` with an exact task-specific path.

For manual creation, prefer an existing repository-local `.worktrees/` or
`worktrees/` directory only when `git check-ignore` proves it is ignored.
Otherwise choose an exact task-specific path outside the repository, following
an existing host or user convention. Do not modify `.gitignore` solely to make
room for a worktree.

Record the chosen absolute path before creation. Ensure it does not already
contain unrelated files and is not a broad directory such as a home,
workspace, or repository root.

## 4. Create the task worktree

If the task branch does not yet exist:

```bash
git worktree add -b <task-branch> <absolute-path> <verified-target-sha>
```

If a matching task branch already exists and is not checked out elsewhere:

```bash
git worktree add <absolute-path> <task-branch>
```

After creation, verify:

```bash
git -C <absolute-path> status --short --branch
git -C <absolute-path> rev-parse HEAD
git -C <absolute-path> branch --show-current
git worktree list --porcelain
```

Confirm the new head equals the intended starting SHA and the task branch is
not accidentally configured to push to the target branch. For a resumed branch,
confirm the new head equals its previously recorded task-tip SHA and recheck
that the target SHA is an ancestor. If Git automatically assigned the target as
the task branch's upstream, unset that upstream and let the first explicit
task-branch push establish the correct one.

If creation fails or any post-creation identity check differs, inspect and
report the exact cause and do not use that worktree. Remove it only when it is
the clean task-owned path created by this attempt; otherwise preserve it for
reconciliation. Do not silently fall back to editing the dirty or protected
original checkout.

## 5. Reconstruct repository prerequisites

Git worktrees do not copy ignored files. Before setup or tests:

- read the repository's maintained setup entrypoint and worktree guidance
- inventory required ignored files, credentials, environment injection,
  binaries, services, ports, and writable caches
- use canonical external secret references or injection mechanisms
- never copy a secret, `.env`, kubeconfig, credential file, or private ignored
  artifact from another checkout into the task worktree
- stop before mutation when a required canonical input cannot be resolved

Run only the repository-maintained setup command needed for this task. Do not
guess a package manager or install dependencies from generic file detection.

## 6. Verify the isolated baseline

Before implementation, confirm:

- the original checkout still has exactly its task-start state
- the worktree is on the intended task branch and starting SHA
- no task file is staged or modified
- required setup completed without creating unexplained tracked changes
- the narrow baseline check required by the repository passes, or its existing
  failure is recorded before task changes

Return the absolute worktree path, branch, target SHA, baseline status, and
setup evidence to `$dev-loop`.

## Ownership and cleanup

Creation does not authorize cleanup. `$finishing-a-development-branch` decides
when the branch and worktree are no longer needed.

- Remove only the exact worktree path recorded by this task and still shown by
  `git worktree list`.
- Inspect tracked, untracked, and ignored contents before removal.
- Never use forced worktree removal to bypass uncommitted or unique files.
- Never prune or delete another worktree merely because it appears stale.
- Preserve a worktree used for an open MR unless the user explicitly requests
  cleanup after confirming its contents are recoverable.
