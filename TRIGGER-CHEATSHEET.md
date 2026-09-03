# Agent Skill Routing

This is the short routing map for the self-maintained development workflow
suite. Load only the Skills needed for the current task.

## Default Development Route

```text
Need autonomy?       long-horizon
Need Plane state?    plane-workflow
Need design pressure? grill-me (explicit only)
Need a delivery brief? create-plan
Need a module seam?  codebase-design
Hard/uncertain bug?  diagnosing-bugs
Need red-green?      tdd
Human-facing prose?  stop-slop
Agent instructions?  writing-for-agents
Implement/change?    dev-loop + lean-delivery
Unknown repository?  guide + existing-project
Unknown scope/flow?  repo-evidence
Atomic commit text?  commit-generate
Committed review?    open-code-review
Push/MR/merge?       finishing-a-development-branch
```

`dev-loop` controls implementation. Git mechanics belong to
`git-workflow-and-versioning`; workspace isolation belongs to
`using-git-worktrees`.

## Choose by Question

| Need | Skill |
| --- | --- |
| Read repository rules and maintained entrypoints | `guide` |
| Define measurable priorities and tradeoffs | `north-star` |
| Stress-test consequential decisions on explicit request | `grill-me` |
| Create an evidence-backed delivery brief | `create-plan` |
| Design module interfaces, ownership, and testing seams | `codebase-design` |
| Prove the cause of a hard, intermittent, or recurring failure | `diagnosing-bugs` |
| Implement observable behavior through a red-green loop | `tdd` |
| Polish README, guides, releases, or design prose | `stop-slop` |
| Design AGENTS, Skill, or agent-runbook instructions | `writing-for-agents` |
| Start a greenfield repository or subsystem | `new-project` |
| Recover an unfamiliar repository map | `existing-project` |
| Find code, callers, dependencies, or impact | `repo-evidence` |
| Govern cross-session or team Memory | `memory-governance` |
| Implement, fix, refactor, or ship | `dev-loop` |
| Continue autonomously with bounded escalation | `long-horizon` |
| Avoid speculative scope and excess abstraction | `lean-delivery` |
| Resolve targets, branches, commits, and versioning | `git-workflow-and-versioning` |
| Create or reuse an isolated worktree | `using-git-worktrees` |
| Draft one staged atomic commit message | `commit-generate` |
| Review one immutable commit with OCR | `open-code-review` |
| Push, open an MR, merge, and clean up | `finishing-a-development-branch` |
| Plan or close Plane WP/Phase evidence | `plane-workflow` |
| Design risk-driven Rust tests | `rust-testing` |
| Recover a Codex active-writer session | `codex-session-writer-recovery` |
| Diagnose ports and process ancestry | `witr-diagnose` |

## Research Route

```text
idea -> research-ideation -> experiment-lab -> plotting/paper-craft
     -> research-comm -> talk-architect -> slidecraft/pptx
```

Use `weekly-report` for commit-based activity summaries.

## Boundary

AnySearch, Workbuddy, Paseo, Lark, visual packs, and other marketplace Skills
are installed external tools. They are not maintained by this repository.
