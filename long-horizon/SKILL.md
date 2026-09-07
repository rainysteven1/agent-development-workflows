---
name: long-horizon
description: "Use when the user explicitly wants Codex to work autonomously with fewer interrupts. Runs a durable evidence-driven harness that continues safe local work, detects real no-progress loops, coordinates reviewers without chasing zero findings, and interrupts only at authority boundaries. Trigger on explicit requests such as \"just do it\", \"be autonomous\", \"don't ask every little thing\", or \"work autonomously for a long time\". 中文触发：自己做、别老问我、自主执行、长时间自主任务、后台做。"
---

# Long Horizon

Use the autonomous harness for the full requested scope. Before taking task
actions, read [references/harness-contract.md](references/harness-contract.md)
completely. That reference is the single source of truth for execution states,
progress detection, reviewer convergence, durable evidence, and human
interrupts; linked workflows must not invent separate retry or approval rules.

## Start the run

1. Fix the objective, observable acceptance checks, trust boundaries, affected
   repositories, and explicitly authorized external actions.
2. Create or reuse the repository/Plane ledger required by the controlling
   workflow. Initialize and maintain every field in the harness contract's
   durable checkpoint, including failure-detector, finding, evidence, approval,
   and resume state.
3. Classify the run with the harness state model and execute the next safe edge.

## Continue autonomously

An explicit long-horizon request is standing authority for local, reversible,
in-scope work. Test failures, review findings, commit/Phase boundaries, retry
counts, timeouts, rate limits, and unavailable quality infrastructure are
observations, not automatic user interrupts.

Keep deterministic acceptance checks as the completion oracle. Reviewers remain
mandatory where the repository requires them, but their findings enter the
shared classifier and finding ledger; reviewer wording, severity, or a target of
zero findings never drives the loop by itself.

## Finish or pause

Continue until the objective is `done`, or until every remaining edge is
`waiting_external` or `waiting_infrastructure`. Pause only the dependent edge;
finish any independent safe work first. `waiting_infrastructure` reports a
resume trigger without asking for permission. Never broaden user authority,
manufacture evidence, close a Plane item with a missing gate, or convert a
fallback review into a formal receipt.

When an interrupt is genuinely required, reuse any matching approval already
recorded for the same action class, scope, and target. Otherwise batch the
unresolved boundary into one concise request that states evidence, surviving
work, and the exact decision needed.
