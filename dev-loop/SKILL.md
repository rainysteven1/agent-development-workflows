---
name: dev-loop
description: "Use when implementing a feature, fix, refactor, or content change in a repo. Drives the work cycle: define acceptance checks, implement, run targeted tests, do a real usage pass, review regressions, and report exactly what was verified or skipped. Trigger on requests like \"implement\", \"fix\", \"refactor\", \"add feature\", \"make this ready\", or \"ship this\". 中文触发：实现、修复、重构、加功能、改一下、做完、可交付。"
---

# Dev Loop

## Overview

Use this skill to keep execution disciplined after coding starts. The point is not just to change files, but to leave behind a clear answer to: what changed, what was verified, and what still carries risk.

## Loop

1. Define the target.
   - Restate the user-visible outcome.
   - Identify the narrowest acceptance checks that would prove the task is done.
   - If the repo already has stronger project rules, follow those first.

2. Implement the smallest useful slice.
   - Prefer incremental changes over a wide refactor unless the task clearly requires it.
   - Reuse local patterns before inventing a new structure.

3. Run targeted verification.
   - Start with the narrowest relevant test or command.
   - Expand to broader checks only when the change surface justifies it.
   - If no automated check exists, create one when the change is important enough.

4. Do a real usage pass.
   - Exercise the changed path the way a user or caller would.
   - For APIs: hit the endpoint or run the client call.
   - For CLIs: run the command on realistic input.
   - For UI: click through the changed flow if tooling allows it.

5. Review for regressions.
   - Check whether the change violates local conventions, broadens scope, or adds hidden coupling.
   - If the task had tradeoffs, note which one was chosen and why.

6. Report the outcome.
   - State what was changed.
   - State what was verified.
   - State what was not verified and why.

## Exit Criteria

Do not treat "code written" as done. A task exits the loop only when:

- the main behavior is implemented
- the most relevant verification ran or the gap is explicitly called out
- the user can see any remaining risk in one pass

## Verification Heuristics

- Small local bug fix: targeted test plus one direct reproduction path
- Medium feature: targeted tests, happy path, one edge case
- Refactor: before/after behavior check plus affected tests
- Risky change: prefer broader verification and explicit rollback notes

## Failure Rules

- If a check fails, fix the issue or narrow the change. Do not hide the failure in the summary.
- If verification is blocked by missing tooling, auth, or environment, say so explicitly and keep the summary concrete.
- If the requested change conflicts with observed repo behavior, stop and surface the conflict instead of guessing.
