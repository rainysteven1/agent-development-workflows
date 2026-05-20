---
name: guide
description: "Use at the start of a session or when repo workflow is unclear. Reads the project's local instructions, active conventions, targets, and task-entry files to produce a concise operational briefing before work begins. Trigger on requests like \"guide\", \"briefing\", \"how do we work here\", \"what skills do we have\", or before a complex task. 中文触发：方法论、工作流、先看规则、项目说明、看看有什么 skill。"
---

# Guide

## Overview

This is a read-only orientation skill. Use it to build a working map of the repo before changing code.

## What To Read

Prefer local project files over generic assumptions:

- `AGENTS.md`, `CLAUDE.md`, `README.md`
- task-specific docs in `docs/`, `notes/`, or repo root
- test, lint, build, and package manager config
- any local skill references or project index files

## Output

Produce a short briefing with:

- repo purpose
- main workflows and commands
- important conventions
- active risks or unknowns
- which skill is likely relevant next

## Rules

- do not modify files
- do not dump raw docs verbatim
- prefer repo facts over generic methodology
- if instructions conflict, surface the conflict explicitly
