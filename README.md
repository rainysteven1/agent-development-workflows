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

## Development Management

| Stage | Skills |
| --- | --- |
| Direction | `guide`, `north-star`, `new-project`, `existing-project` |
| Evidence | `repo-evidence`, `memory-governance` |
| Delivery control | `dev-loop`, `long-horizon`, `lean-delivery` |
| Git mechanics | `git-workflow-and-versioning`, `using-git-worktrees`, `commit-generate` |
| Review and integration | `open-code-review`, `finishing-a-development-branch` |
| Planning and closure | `plane-workflow` |
| Engineering quality | `rust-testing` |
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
  -> plane-workflow
  -> dev-loop + lean-delivery
  -> repo-evidence when scope or relationships are uncertain
  -> commit-generate
  -> open-code-review
  -> finishing-a-development-branch
```

`dev-loop` is the controlling implementation workflow. The other Skills own
specialized decisions; they do not create parallel delivery loops.

## Repository Contract

- Edit a Skill here, not in an installed copy.
- Keep one independently reviewable reason per commit.
- Validate every changed Skill with the system `skill-creator` validator and
  execute its changed scripts or tests.
- Run immutable per-commit review before integration.
- Synchronize only repository-owned Skills to agent hosts. Never overwrite or
  delete unrelated third-party Skills in those hosts.
- Keep credentials, Memory keys, runtime state, review receipts, and generated
  caches outside Git.

Each Skill directory contains a required `SKILL.md` and only the scripts,
references, assets, evaluation cases, or UI metadata that its maintained
workflow needs.

See `TRIGGER-CHEATSHEET.md` or `TRIGGER-CHEATSHEET.zh-CN.md` for concise routing.
