# Agent Development Workflows

This repository is the source of truth for Rainy's self-maintained agent
Skills. It covers the complete development-management loop: orientation,
repository evidence, implementation, Git isolation, review, Plane evidence,
integration, testing, diagnostics, and research delivery.

The repository is client-neutral. Codex, Claude-compatible clients, CC Switch,
and other agent hosts are deployment targets; their installed Skill directories
are not sources of truth.

## Ownership Boundary

Every Skill committed here is maintained as part of this workflow suite. Do not
vendor provider or marketplace Skills merely because they are installed on one
machine. AnySearch, Workbuddy, Paseo, Lark, visual-design packs, and Android
testing packs remain external dependencies and keep their own update channels.

An externally inspired Skill belongs here only after its maintained behavior
has been rewritten for this suite and this repository accepts responsibility
for its tests, review, and future changes.

## Quick Start

For an ordinary repository change, describe the outcome directly. You do not
need to name the delivery Skills:

> Add CSV export to the user list, verify it through the real CLI, and finish
> the local change.

`dev-loop` activates for implementation and repository content changes. It is
the delivery controller: it invokes a linked Skill only when the task reaches
the stage or condition that Skill owns. It does not run every Skill on every
change.

### Choose an entry point

| Situation | Start with | Example |
| --- | --- | --- |
| Routine feature, fix, refactor, or documentation change | No explicit Skill | `Add CSV export and verify it.` |
| Work autonomously with fewer interruptions | `$long-horizon` | `$long-horizon complete the current Plane Phase.` |
| Stress-test consequential decisions before planning | `$grill-me` | `$grill-me challenge this cache design; do not implement it.` |
| Turn settled direction into a reviewable delivery brief | `$create-plan` | `$create-plan produce a Plane-ready plan for this design.` |
| Publish an approved design and split delivery work | `$plane-workflow` | `$plane-workflow publish this design and create its WP and Phases.` |
| Diagnose a hard, intermittent, or recurring failure | `$diagnosing-bugs` | `$diagnosing-bugs find the root cause; diagnose only.` |
| Require a test-first behavior change | `$tdd` | `$tdd add CSV export through a red-green loop.` |
| Rework module ownership, interfaces, or test seams | `$codebase-design` | `$codebase-design reduce the mocks required by this interface.` |
| Polish a README, guide, release note, or design narrative | `$stop-slop` | `$stop-slop polish this README without changing commands or facts.` |
| Improve AGENTS, Skills, or an agent runbook | `$writing-for-agents` | `$writing-for-agents reduce routing ambiguity in AGENTS.md.` |

`$grill-me` is explicit-only. The other Skills may be selected implicitly when
their descriptions match, or reached from the controlling workflow.

### What `dev-loop` invokes

For a material repository change, the normal delivery path uses:

- `$git-workflow-and-versioning` to resolve the target and commit boundaries;
- `$using-git-worktrees` only when the current checkout needs isolation;
- `$lean-delivery` to keep the implementation acceptance-complete and small;
- `$commit-generate` after one atomic increment is staged;
- `$open-code-review` after each material commit; and
- `$finishing-a-development-branch` for the authorized push, MR, merge, or
  local integration handoff.

The controller adds specialized Skills only when their condition is present:

- `$repo-evidence` when repository scope, location, callers, dependencies, or
  impact are unclear, and for cross-module refactors, deletions, or other
  graph-sensitive changes;
- `$create-plan` when a material design is not settled;
- `$codebase-design` when module ownership, an interface, or a test seam is the
  unresolved problem;
- `$diagnosing-bugs` before correcting a hard or uncertain failure;
- `$tdd` when observable behavior has a stable seam for a red-green loop;
- `$writing-for-agents` for agent-facing instructions; and
- `$stop-slop` for human-facing technical prose within its declared scope.

A small, direct change takes the short route. A green test suite does not
replace an unmapped acceptance criterion, and an optional Skill never replaces
the Git, review, or completion gates owned by `dev-loop`.

## Development Management

| Stage | Skills |
| --- | --- |
| Direction | `guide`, `north-star`, `new-project`, `existing-project` |
| Evidence | `repo-evidence`, `memory-governance` |
| Design intake | `grill-me`, `create-plan`, `codebase-design` |
| Delivery control | `dev-loop`, `long-horizon`, `lean-delivery` |
| Git mechanics | `git-workflow-and-versioning`, `using-git-worktrees`, `commit-generate` |
| Review and integration | `open-code-review`, `finishing-a-development-branch` |
| Planning and closure | `create-plan`, `plane-workflow` |
| Engineering quality | `codebase-design`, `tdd`, `diagnosing-bugs`, `rust-testing` |
| Writing quality | `stop-slop`, `writing-for-agents` |
| Local diagnostics | `codex-session-writer-recovery`, `witr-diagnose` |

## Research and Communication

| Area | Skills |
| --- | --- |
| Research lifecycle | `research-ideation`, `experiment-lab`, `paper-craft` |
| Results and figures | `plotting` |
| Communication | `research-comm`, `talk-architect`, `slidecraft`, `pptx` |
| Reporting | `weekly-report` |

## Default Daily Stack

For an autonomous Plane-managed implementation, start with:

```text
long-horizon
  -> grill-me when explicitly requested
  -> create-plan for material design
  -> plane-workflow when Plane is the authority
  -> dev-loop + lean-delivery
  -> repo-evidence when scope or relationships are uncertain
  -> codebase-design when interfaces or seams are uncertain
  -> diagnosing-bugs before fixing hard failures
  -> tdd for observable behavior at a stable seam
  -> commit-generate
  -> open-code-review
  -> finishing-a-development-branch
```

`dev-loop` is the controlling implementation workflow. The other Skills own
specialized decisions; they do not create parallel delivery loops.

An approved `$create-plan` brief may be published through `$plane-workflow`.
After Page and hierarchy read-back verification, Plane is the execution
authority; later material design drift must be reconciled there before work
continues.

## Repository Contract

- Edit a Skill here, not in an installed copy.
- Keep one independently reviewable reason per commit.
- Validate every changed Skill with the system `skill-creator` validator and
  execute its changed scripts or tests.
- Use `writing-for-agents` for instruction routing and completion behavior;
  apply `stop-slop` only to human-facing prose after semantics are fixed.
- Run immutable per-commit review before integration.
- Synchronize only repository-owned Skills to agent hosts. Never overwrite or
  delete unrelated third-party Skills in those hosts.
- Keep credentials, Memory keys, runtime state, review receipts, and generated
  caches outside Git.

Each Skill directory contains a required `SKILL.md` and only the scripts,
references, assets, evaluation cases, or UI metadata that its maintained
workflow needs.

See `TRIGGER-CHEATSHEET.md` or `TRIGGER-CHEATSHEET.zh-CN.md` for concise routing.
