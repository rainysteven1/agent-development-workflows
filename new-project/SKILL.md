---
name: new-project
description: "Use when starting a greenfield code project or major subsystem. Elicit requirements, choose a minimal first slice, define interfaces, scaffold structure, and track requirements in a lightweight index that can grow with the project. Trigger on \"start from scratch\", \"init project\", \"scaffold this\", or first-iteration planning. 中文触发：新项目、从零开始、项目初始化、脚手架、第一版设计。"
---

# New Project

## Overview

Use this skill to keep a new project grounded in explicit requirements instead of premature architecture. The goal is to define just enough structure to support the first real slice of work.

## Workflow

1. Define the first useful outcome.
   - What must the first version actually do?
   - What is explicitly out of scope?
   - What constraints already exist: language, runtime, hosting, deadlines, compatibility?

2. Capture requirements in a form proportional to the project size.
   - Small project: a short markdown checklist can be enough.
   - Multi-feature project: use `project-index.yaml` from the start.

3. Design interfaces before filling in implementation.
   - Choose module boundaries and public entrypoints.
   - Keep the first structure simple enough to refactor.

4. Build the thinnest vertical slice.
   - Prefer one end-to-end path over many disconnected stubs.
   - Write tests that prove the requirement, not the implementation detail.

5. Update the requirement map as code lands.
   - Requirement -> code path
   - Requirement -> tests
   - Requirement -> docs if any

## Practical Rules

- Avoid speculative abstractions in the first iteration.
- Prefer boring defaults unless the repo has a strong reason not to.
- Record non-goals. They prevent scope creep as much as requirements do.
- If the first slice exposes a structural mistake, refactor early while the surface is still small.

## Suggested Artifacts

- `project-index.yaml` for structured projects
- `docs/requirements.md` for lightweight requirement capture
- `AGENTS.md` for repo-specific workflow rules

## Exit Condition For Setup

Project setup is complete when:

- the first slice is clearly scoped
- the main interfaces are named
- the repo has enough structure to implement without guesswork
- requirements have a durable home in the tree
