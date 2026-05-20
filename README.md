# Codex Skills Selected

This directory contains Codex-adapted skills migrated from the `skills-main` Claude skill pack.

## Included Skills

### Software Development

| Skill | Purpose |
|---|---|
| `guide` | Brief the repo's workflow, conventions, and likely next skill before work starts |
| `dev-loop` | Drive implementation, verification, and completion reporting |
| `north-star` | Define measurable project objectives and tradeoff rules |
| `long-horizon` | Run with higher autonomy and controlled escalation |
| `new-project` | Scope and scaffold a greenfield project or subsystem |
| `existing-project` | Recover intent and working context from an unfamiliar codebase |

### Research

| Skill | Purpose |
|---|---|
| `research-ideation` | Turn research hunches into testable hypotheses |
| `experiment-lab` | Plan, track, compare, and interpret experiments |
| `paper-craft` | Draft and polish papers with claim-evidence consistency |
| `research-comm` | Prepare advisor, coauthor, or meeting updates |
| `talk-architect` | Plan an academic talk before building slides |
| `slidecraft` | Build and diagnose academic decks and slide structure |
| `plotting` | Create publication-quality figures |
| `pptx` | Handle native `.pptx` editing, extraction, and QA |

### Reporting

| Skill | Purpose |
|---|---|
| `weekly-report` | Generate weekly work reports from commit history |

## Structure

Each skill folder contains:

- `SKILL.md`: the Codex-facing skill instructions
- `agents/openai.yaml`: UI metadata for Codex skill discovery

Quick reference files in this directory:

- `TRIGGER-CHEATSHEET.md`: short English routing guide
- `TRIGGER-CHEATSHEET.zh-CN.md`: Chinese routing guide

## Source Notes

- These skills were adapted for Codex, not copied verbatim from the Claude plugin.
- Claude-plugin-specific automation such as auto-harness hooks, notification plumbing, and skill telemetry was intentionally omitted.
- The training-only skill `areal-rl` was not included in this pack.

## Validation

All skill folders in this directory passed `quick_validate.py` from the local `skill-creator` system skill.
