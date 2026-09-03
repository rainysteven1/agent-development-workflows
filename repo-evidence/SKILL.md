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

Run the read-only capability inventory when tool state is unknown:

```bash
python ~/.codex/skills/repo-evidence/scripts/capabilities.py --repo "$PWD"
```

See [references/tools.md](references/tools.md) for provider-specific commands
and interpretation.

## Return an evidence packet

Report the question, immutable revision when applicable, routes used, candidate
paths, verified source/test paths, checks actually run, index state, conflicts,
and remaining blind spots. Never upgrade an unexecuted check into proof.
