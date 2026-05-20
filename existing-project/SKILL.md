---
name: existing-project
description: "Use when taking over an unfamiliar or legacy codebase. Recover requirements from code, tests, and docs; identify entrypoints and active modules; map conflicts; and create a lightweight project index before changing behavior. Trigger on onboarding, legacy maintenance, audits, and \"figure out how this repo works\". 中文触发：接手项目、老项目、存量代码、看懂这个仓库、审计代码。"
---

# Existing Project

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

2. Mark active and risky areas.
   - Look for recent commits, failing tests, large modules, compatibility layers, and TODO clusters.
   - Note modules that seem central to the current task.

3. Reconstruct requirements coarsely.
   - For each major area, write down what it appears to do.
   - Label confidence as `confirmed`, `inferred`, or `uncertain`.

4. Record conflicts instead of silently resolving them.
   - Example: code says 60 req/min, docs say 100 req/min.
   - Keep the discrepancy visible until the user or code path clarifies the intent.

5. Create a lightweight index if none exists.
   - For larger repos, use `project-index.yaml`.
   - For smaller repos, a markdown table in `docs/project-map.md` is enough.

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
