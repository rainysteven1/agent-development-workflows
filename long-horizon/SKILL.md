---
name: long-horizon
description: "Use when the user wants Codex to work autonomously with fewer interrupts. Provides a decision ladder from convention check to user escalation, plus lightweight decision logging so longer tasks can continue without constant approval requests. Trigger on \"just do it\", \"be autonomous\", \"don't ask every little thing\", or long-running implementation work. 中文触发：自己做、别老问我、自主执行、长时间任务、后台做。"
---

# Long Horizon

## Overview

This skill defines how to make progress without consuming the user's attention too early. The rule is simple: exhaust cheap evidence before escalating.

## Decision Ladder

1. `Convention check`
   - Look for repo rules, existing patterns, config files, and adjacent code.
   - If the answer is already local and clear, follow it silently.

2. `Codebase research`
   - Read the related modules, tests, docs, and recent history.
   - Use this level for implementation patterns and behavior expectations.

3. `External research`
   - Read official docs or primary sources when the repo is silent.
   - Use this for framework behavior, library choices, and ecosystem questions.

4. `Objective reasoning`
   - If multiple paths are valid, choose using the active project targets.
   - Prefer the option that preserves correctness and reduces future complexity.

5. `Ask the user`
   - Use only for product intent, missing credentials, irreversible actions, or unresolved ambiguity after the earlier levels.

## Logging Rule

Record meaningful Level 2+ decisions in a durable place when the task is long or the tradeoff is non-obvious.

Good options:

- `docs/decisions.md`
- a dated note in `notes/`
- the final task summary if no project note exists

A short entry is enough:

```text
Decision: chose zod over joi
Basis: external research
Reason: better TypeScript inference, lower duplication
```

## Escalation Rule

When you do ask the user:

- batch related questions together
- show what you already checked
- present the decision boundary, not raw confusion

Bad:

```text
Should I use headers or cookies?
```

Better:

```text
Current browser clients use cookies, the new API work would be cleaner with headers,
and the repo has no explicit rule. Which compatibility target matters more?
```

## Anti-Patterns

- asking before checking local conventions
- making important tradeoffs with no visible reasoning
- spending too long researching a low-value decision
- escalating one question at a time
