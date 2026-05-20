---
name: north-star
description: "Use when project priorities are unclear, before a larger implementation, or during repo onboarding. Helps define 1-3 measurable objectives, observation mechanisms, baselines, and tradeoff rules so Codex can optimize for what actually matters. Trigger on goals, priorities, metrics, quality targets, and questions like \"what should we focus on\". 中文触发：目标、优先级、指标、方向、关注什么、质量标准。"
---

# North Star

## Overview

Use this skill to turn vague priorities into a small set of measurable targets. A project without explicit targets drifts toward whichever request was most recent.

Keep the set small: one to three targets. More than that usually means the project has not actually prioritized.

## Build Targets From Observables

Before defining targets, inventory what the repo can already observe:

- `script`: test runners, linters, coverage, build output, static analysis, benchmarks
- `agent`: structured review prompts for clarity, test relevance, API consistency
- `human`: UX feel, product fit, naming preference, strategic direction

If a target has no repeatable way to observe it, it is not ready.

## Target Template

For each target, capture:

- `Target`: the thing being optimized
- `Indicator`: a number or checkable condition
- `Mechanism`: script, agent, or human
- `Baseline`: the current value
- `Constraint`: what must stay fixed for future comparisons

Example:

```text
Target: Maintainability
Indicator: Average function complexity
Mechanism: script - radon cc src/ -a
Baseline: 4.8 on 2026-05-20
Constraint: Same tree, same config, same command
```

## Workflow

1. Scan the repo and list available observables.
2. Ask which qualities the user actually cares about.
3. Collapse those answers into 1-3 targets.
4. Measure the baseline before optimizing.
5. Use the targets to break ties in future decisions.

## Good Defaults

- Backend: correctness, maintainability, latency
- Frontend: task success, accessibility, bundle size
- Library: API clarity, compatibility, test coverage
- Internal tool: operator speed, error recovery, simplicity

## Storage

Record targets somewhere durable in the repo. Good options:

- `AGENTS.md` for working rules
- `project-index.yaml` for structured tracking
- `docs/metrics.md` for a lightweight project note

If the repo is small, a short markdown block is enough. Do not force a heavy schema when a simple file will do.

## Decision Rule

When two valid approaches compete, prefer the one that improves or preserves the active targets with the least extra complexity.
