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

## Recovery Workflow

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
   - Keep it task-owned and ignored by default.
   - Add `project-index.yaml` or `docs/project-map.md` to the repository only
     when the user authorizes a durable documentation change.

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
