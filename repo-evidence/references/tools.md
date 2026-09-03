# Repository evidence tools

## FastCtx and ripgrep

Use FastCtx `grep`, `glob`, and `inspect_local_file` for exact repository facts.
Use `rg` when a maintained shell workflow or Git-aware command pipeline needs
it. Exact search remains the final negative-search check for generated files,
configuration, scripts, reflection, and cross-language boundaries.

## Zvec-Grep (`zg`)

Zvec-Grep unifies indexed BM25 and vector retrieval with managed ripgrep.

```bash
zg status "$repo" --mode direct --check-ready
zg query "natural-language intent" --limit 7 --refresh off --mode direct
zg query --fts "ExactSymbol" --limit 7 --mode direct
zg query --rg -F "ExactSymbol" path/to/scope
```

Use indexed discovery when wording or location is unknown or evidence spans
files. Use native FastCtx/rg for an exact word, symbol, path, or regex. Read and
verify every material hit in source.

Create an index only with explicit task authority. The default private-code
profile is local CPU embedding:

```bash
zg index "$repo" --embedding local/potion-code-16m-v2 --device cpu --mode direct
```

Record model, dimensions, coverage, pending/failed items, storage path, build
time, and disk size. Never add `--allow-remote`, an endpoint, or an API key for
private code without explicit user authorization.

An existing canonical index is queried from its canonical root even while the
task checkout is elsewhere. Treat returned paths as candidates in that baseline
revision, translate them to repository-relative paths, and read the
corresponding task-worktree files before drawing a conclusion. Because the
workspace manifest is root-bound, never rsync or reflink `.zvec-grep` into a
different worktree.

## Graft

Graft's normal build creates a deterministic tree-sitter graph. Optional deep
context and LSP edges are separate layers and must be reported separately.

```bash
graft build "$repo"
graft check "$repo" --json
graft map "$repo"
graft ask "task or concept" "$repo" --json
graft callers Symbol "$repo"
graft blast "$repo" --base origin/main --format json
```

`graft check` is the read-only drift report. Queries may refresh working-tree
state automatically; that is not immutable evidence. Structural readiness can
be valid while optional context enrichment is missing or pending. Preserve that
distinction in reports.

For a managed task worktree, inherit only a clean canonical `graft/` plus its
compatible `.graft/` configuration as a new task-owned snapshot. Prefer a
filesystem reflink when available, otherwise a non-linking copy such as rsync
without `--delete`. Refuse a non-empty destination, shared symlink, dirty
baseline, different Git common directory, or incompatible configuration. When
the current task or recorded managed-index policy authorizes maintaining this
existing snapshot, run `graft build "$task_repo"` followed by
`graft check "$task_repo" --json`; both commands must succeed. Creating
structural state without a reusable snapshot requires separate explicit index
creation authority. The blocking check, not the transfer, establishes task
freshness.

After a verified merge, refresh each existing canonical baseline once from the
clean merged target. Do not feed a task cache back into the canonical worktree.

## Memory boundary

Memory can suggest prior decisions, terminology, preferences, and failure
patterns. Route all persistent reads, writes, promotion, sharing, revocation,
and conflict handling through `$memory-governance`. Reconfirm code claims at the
current repository state.
