---
name: finishing-a-development-branch
description: "Finish a verified task branch by rechecking its target, complete commit range, current head, review and test evidence, then perform the user-authorized handoff: keep it, push/open or update an MR, merge locally, or merge an approved MR. Use only after dev-loop implementation and finding disposition are complete. Owns integration and cleanup mechanics, not implementation or commit creation."
---

# Finishing a Development Branch

Integrate only the exact verified revision into the exact verified target.
`$dev-loop` supplies the completed branch evidence and
`$git-workflow-and-versioning` supplies the target and commit range.

## 1. Require a finish packet

Before offering or executing an integration action, require:

- repository and remote
- task branch and full current head SHA
- intended target branch and its last verified full SHA
- merge base, ordered commit list, and complete target-to-head diff
- clean task status or an explicit list of intentionally uncommitted artifacts
- targeted and final verification tied to the current head
- independent review conclusion and every finding disposition when review
  applies
- any required external gate, receipt, approval, or deployment prerequisite

If a required item is absent or stale, return to `$dev-loop`. Do not interpret
"implementation looks finished" as evidence.

## 2. Recheck immutable inputs

Immediately before an external action:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse <authoritative-target-ref>^{commit}
git merge-base <authoritative-target-ref> HEAD
git log --oneline --decorate <target>..HEAD
git diff --stat <target>...HEAD
```

Confirm the task head still matches every test, review, and CI result being
used. First refresh the authoritative remote or forge state required by the
authorized handoff. Resolve the current target branch to a full SHA, compare it
with the finish packet, and verify the MR target and source head again. A stale
local remote-tracking ref is not authoritative evidence.

If the current target SHA differs from the finish packet, stop the handoff,
recompute the merge base and complete range, follow the repository's documented
update policy, and rerun every check, review, CI gate, or receipt invalidated by
that movement. Never rewrite or force-push shared history merely to make the
branch appear current.

## 3. Select only an authorized handoff

If the user already requested a specific push, MR, or merge action, execute
that action once its gates pass. Otherwise present the applicable choices:

1. keep the branch and worktree for later
2. push the task branch and open or update an MR against the verified target
3. merge locally into the verified target

Offer MR merge only when an MR already exists and the user has asked to merge
it. Discarding work is never a routine finish option and requires a separate,
explicit request identifying the exact branch and worktree.

## 4. Push and open or update an MR

- Push the task branch to a same-named remote branch; do not rely on an
  upstream that points at the integration target.
- Create or update the MR with the verified target branch, complete change
  summary, validation evidence, and issue or planning references required by
  the repository.
- Re-read the MR after mutation and confirm its source branch, full head SHA,
  target branch, and URL.
- Keep the task worktree while the MR is open so review feedback remains
  isolated from the user's original checkout.

## 5. Merge an MR

Immediately before merge, require all applicable gates to be current and
passed:

- MR target is the verified integration target
- source head SHA equals the reviewed and tested head
- required CI is green for that exact head
- required approvals are present
- no blocking review finding remains
- required planning receipt or state update has been written and re-read
- mergeability and repository policy permit the selected merge method

Re-read the source head after checking the gates. If it changed, stop and
invalidate the older CI, review, and receipt evidence.

After merge, verify the forge reports the expected merged state and that the
target contains the intended task revision or merge result. Run post-merge
checks only when the repository contract or task requires them.

## 6. Merge locally

Use this only when the user explicitly chooses local integration.

- Move to a clean checkout of the verified target without disturbing another
  worktree's user baseline.
- Update the target according to repository policy.
- Merge using the repository's required strategy.
- Verify the merged result with the checks invalidated by integration.

If the merge or verification fails, stop with the branch and worktree intact.
Do not push the failed result or remove recovery evidence.

## 7. Cleanup

Cleanup is allowed only after verified integration or a separately confirmed
discard request.

- Keep the worktree for an open or unmerged MR.
- Before removal, inspect tracked, untracked, and ignored files in the exact
  task-owned worktree.
- Remove only the recorded task worktree after proving it has no unique
  content. Never force removal to bypass that check.
- Delete only the exact merged task branch, using a non-forcing delete unless
  the user explicitly authorized destruction after reviewing what would be
  lost.
- Do not prune or delete unrelated worktrees, branches, caches, or directories.

## Completion evidence

Report the final target, task head, MR URL when applicable, CI and review
conclusions, integration result, post-action verification, and cleanup state.
If any required gate did not pass, report the branch as not complete and name
the first unpassed checkpoint.
