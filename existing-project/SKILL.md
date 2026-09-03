---
name: existing-project
description: "Use when taking over an unfamiliar or legacy codebase. Recover requirements from code, tests, and docs; identify entrypoints and active modules; map conflicts; and create a lightweight project index before changing behavior. Trigger on onboarding, legacy maintenance, audits, and \"figure out how this repo works\". 中文触发：接手项目、老项目、存量代码、看懂这个仓库、审计代码。"
---

# Existing Project

Use `$repo-evidence` for repository discovery and evidence quality. This skill
owns the recovered project map; `$repo-evidence` owns exact, semantic, and
structural discovery.

## Overview

The main problem in an existing repo is missing context. This skill is for reconstructing enough truth to work safely before making behavior changes.

## Truth Order

When sources disagree, use this order:

```text
code > tests > docs
```

Code is what actually runs. Tests are claims with executable evidence. Docs are useful, but often stale.

## Choose the recovery mode

Use full bootstrap only when the repository has no usable project map, the map
cannot be tied to the same Git repository and a known revision, or architecture
has drifted beyond its recorded coverage. A newly created worktree is not by
itself a new repository and does not justify full recovery.

Use resume/delta when a canonical project map exists. Require it to record the
repository common Git directory, canonical worktree, baseline revision, mapped
areas, commands, evidence-index state, and known blind spots. Reject a map from
another common Git directory or one whose baseline commit is unavailable.

Escalate resume/delta to full bootstrap only when one of these is observed:

- the map is missing, corrupt, or cannot be bound to the repository;
- the task enters an unmapped subsystem whose entrypoints cannot be recovered
  with a focused trace;
- build, workspace, module, or deployment structure changed materially since
  the baseline; or
- the baseline-to-task delta is too large or non-contiguous to explain safely.

## Full bootstrap workflow

1. Perform a shallow survey.
   - Identify entrypoints, module boundaries, build commands, test commands, and deployment clues.
   - Read only enough to build a map before diving into details.

2. Discover unknown concepts and relationships.
   - Use exact FastCtx search when names or paths are known.
   - Use semantic discovery only when wording or location is unknown.
   - Use a structural graph only for callers, dependencies, impact, or module boundaries.
   - Read the candidate source and tests before accepting a requirement claim.

3. Mark active and risky areas.
   - Look for recent commits, failing tests, large modules, compatibility layers, and TODO clusters.
   - Note modules that seem central to the current task.

4. Reconstruct requirements coarsely.
   - For each major area, write down what it appears to do.
   - Label confidence as `confirmed`, `inferred`, or `uncertain`.

5. Record conflicts instead of silently resolving them.
   - Example: code says 60 req/min, docs say 100 req/min.
   - Keep the discrepancy visible until the user or code path clarifies the intent.

6. Create a lightweight project map if none exists.
   - Keep a reusable local map beside the canonical main worktree, ignored by
     Git, unless the repository already maintains a versioned map.
   - Record the common Git directory, canonical worktree, exact baseline SHA,
     coverage, commands, evidence-index locations, and blind spots.
   - Add `project-index.yaml` or `docs/project-map.md` to the repository only
     when the user authorizes a durable documentation change.

## Resume/delta workflow

1. Read the closest instructions and the reusable project map; do not repeat the
   full shallow survey.
2. Verify the task worktree and canonical worktree share the recorded Git common
   directory, and that the map's baseline revision still exists.
3. Inspect instruction changes and the baseline-to-task name/status diff. Trace
   only changed paths, the current task area, its direct consumers, and newly
   introduced entrypoints or automation.
4. Ask `$repo-evidence` for current and baseline index state. Reuse the canonical
   semantic baseline and refresh only task-local structural evidence as its
   contract permits.
   - When the Git common directory has managed index configuration, read
     `index_lifecycle.py status`. A ready post-checkout result replaces manual
     snapshot copying; an absent/failed task state must be repaired with the
     maintained `prepare-worktree --apply` command before graph-dependent work.
5. Return the inherited map plus a delta appendix: task HEAD, changed coverage,
   confirmed commands, conflicts, stale areas, and the condition that would
   require full bootstrap.

Do not rewrite the reusable baseline map from an unmerged task worktree. Refine
it after integration from the updated canonical worktree, or keep task-only
discoveries in the ignored task ledger.

## What To Capture

For each recovered requirement or subsystem, keep:

- short title
- source evidence
- owning files
- related tests
- confidence level
- open conflicts or open questions

## Working Rule

Do not wait for a perfect map before starting useful work. Aim for a usable map:

- every major module has a rough purpose
- the current task area is understood well enough to change safely
- important contradictions are written down

Refine the map as you touch code. Recovery is ongoing, not a one-time ceremony.
