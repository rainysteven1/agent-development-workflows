---
name: repo-evidence
description: "Route repository evidence gathering across exact search, semantic discovery, structural graphs, source verification, and revision-bound proof. Use when code location, callers, dependencies, impact, or repository scope is uncertain. Do not use for external web facts, implementation control, Git integration, review verdicts, or persistent Memory writes."
---

# Repository Evidence

Find the smallest reliable evidence path for a repository question. This skill
owns discovery and evidence quality, not implementation, Git mechanics, formal
review, or persistent Memory lifecycle.

## Evidence ladder

Treat sources according to what they can prove:

1. **Hint** - Memory, old chat, or historical documentation. Use it to form a
   search direction and label it as unverified.
2. **Candidate** - semantic or ranked retrieval such as Zvec-Grep. Use it to
   locate likely files, symbols, and vocabulary.
3. **Structural** - Graft callers, dependency paths, maps, and blast radius.
   Use it to identify relationships and impact candidates.
4. **Verified** - source, tests, configuration, generated entrypoints, and raw
   exact search read at the current repository state.
5. **Proven** - a check, build, test, or real run bound to an immutable revision.

Hints and candidates may appear in an exploratory report only when clearly
labelled. They cannot support behavior, safe-deletion, or completion claims.
A graph with no edge is not proof that no consumer exists.

## Route the question

- Exact identifier, text, path, filename, or regex: use FastCtx or `rg` first.
- Natural-language intent with unknown wording or location: use Zvec-Grep,
  then read the returned source with FastCtx.
- Callers, callees, dependencies, cross-module impact, or deletion scope: use
  Graft, then confirm with exact search, source, compiler/type checks, tests,
  generated/configuration entrypoints, and known cross-repository consumers.
- External current facts: leave this skill and use `$openai-docs` for OpenAI or
  `$anysearch` for other primary sources.
- Persistent experience or preferences: use `$memory-governance`; Memory is a
  hint and never current-code authority.

Start with one discovery route. Add a structural route only when the question
requires relationships. Use a second derived index only for an explicit
high-risk cross-check or a demonstrated conflict.

## Fix the repository state

Before relying on an index, record:

- repository root and full `HEAD`
- dirty-worktree state
- tool path and version
- index readiness, coverage, model or graph layer, and pending/failed work
- known language, generated-code, dynamic-call, submodule, and external-consumer
  blind spots

Graft describes working-tree bytes and may include uncommitted edits. That is
useful during development. For immutable completion evidence, require a clean
worktree at the claimed `HEAD`, rebuild or refresh as maintained by the tool,
and require `graft check` structural freshness. Do not invent a Graft revision
field that the installed version does not expose.

Zvec-Grep semantic search requires a ready workspace index. Prefer a local
embedding model. Remote embeddings require explicit user authorization because
repository content leaves the machine. Index creation, rebuild, and deletion
are explicit mutations; the MCP search tool must not perform them implicitly.

## Reuse indexes across worktrees

Treat a bare repository as Git object/ref authority only. It has no source tree
and must never be used as a Graft or Zvec-Grep indexing root. A managed
worktree topology has three roles:

```text
<repository>.git/       bare common Git directory
<repository>/           clean canonical target worktree and full index baseline
<repository>-<wp>/      writable task worktree and task-local delta evidence
```

Resolve the canonical worktree from a maintained project map or repository
configuration. Do not infer it merely from a directory name. Verify that it and
the task worktree share the same resolved Git common directory, and record both
full revisions and dirty states before reuse.

The first explicitly authorized bootstrap establishes the managed baseline and
records its model/configuration. Refresh that existing canonical baseline only
after verified integration, keyed by the integrated revision; skip a retry when
that revision already has a successful convergence record. Changing the model,
rebuilding, dropping, or creating a new persistent index still requires
explicit authority.

Graft caches use repository-relative source paths and may be inherited only as
a private task snapshot. Copy or reflink a clean, ready canonical snapshot into
an absent task-local cache; never symlink or share one writable cache between
worktrees. Immediately run the installed version's blocking refresh/check in
the task worktree. If the snapshot is incompatible, discard only that proven
task-owned copy and build task-local structural state instead. Never claim a
copy operation itself as freshness evidence.

Zvec-Grep stores root-bound workspace metadata and absolute source paths. Do not
copy `.zvec-grep` between worktrees. Query the canonical index for stable
repository-wide semantic discovery, then verify every candidate against the
task worktree with source/exact search and, when needed, task-local Graft. Build
a scoped task-local Zvec-Grep index only when branch-only content genuinely
needs semantic discovery and the current task authorizes that mutation.

After integration, update the canonical target worktree to the verified merged
revision and refresh its existing Graft and Zvec-Grep baselines once. Never
copy a task Zvec-Grep index back. Cleanup may remove only the recorded
task-owned snapshot after proving no other worktree uses it.

Run the read-only capability inventory when tool state is unknown. Pass the
recorded canonical worktree in resume/delta mode:

```bash
python ~/.codex/skills/repo-evidence/scripts/capabilities.py --repo "$PWD"
python ~/.codex/skills/repo-evidence/scripts/capabilities.py \
  --repo "$PWD" --baseline-repo /absolute/canonical/worktree
```

See [references/tools.md](references/tools.md) for provider-specific commands
and interpretation.

## Return an evidence packet

Report the question, immutable revision when applicable, worktree role,
canonical baseline path/revision, common-directory match, routes used, candidate
paths, verified source/test paths, checks actually run, index origin/freshness,
conflicts, and remaining blind spots. Never upgrade an unexecuted check or cache
copy into proof.
