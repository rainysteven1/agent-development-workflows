# Repository-Local Plane Routing

Plane ownership is repository-specific. Keep shared Plane transport and authentication only in
`~/.config/surveying/plane.env` with mode `600`; it must not select a workspace or project.

## Resolve before calling Plane

Use this order:

1. Read the closest repository `.codex/config.toml`, `.plane-workflow.json`, `AGENTS.md`, project index, delivery docs, and
   checked-in Plane mapping.
2. Search the repository for an exact Plane URL, workspace slug, project UUID, identifier, or stable
   project external ID.
3. Verify the resolved project by reading its name, workspace, and retained Pages/Modules/Work Items.
4. If the repository has no authoritative mapping, stop before writes. Establish and record the
   repository-local mapping from verified ownership evidence or explicit user direction first.

Do not infer ownership from the product name, parent directory, current MCP process, or a similarly
named project.

## Configuration placement

- Store only `PLANE_BASE_URL` and `PLANE_API_KEY` in the canonical user-level `plane.env`. Do not
  duplicate them in `~/.codex/config.toml`, repository config, worktrees, or shell history.
- Store `PLANE_WORKSPACE_SLUG` in the repository-local `.codex/config.toml`. Store the authoritative
  project UUID/identifier and ownership evidence in the closest repository `AGENTS.md` or project
  index.
- When a task crosses repositories, resolve each repository independently. One task may legitimately
  update more than one Plane project.

## Route selection

After resolving repository ownership, use the tools configured by that repository. If the current
MCP process was started without the repository-local workspace, restart it from the repository
context; do not rewrite user-level configuration or fall back to another workspace.

For the installed self-hosted Plane release, project Page creation uses the bundled in-cluster
serializer helper because the public Page endpoint is absent. Supply the resolved workspace and
project UUID; never hardcode one repository's values into the general skill. The helper is read-only
by default; creation requires explicit `--apply`.

## Verification

Before any write, report or internally assert:

- repository path;
- resolved workspace slug;
- resolved project UUID and exact name;
- evidence source for that mapping;
- whether the project is archived and whether retained items were re-listed after restoration.

If any value conflicts with a repository-local mapping or a user-provided Plane URL, stop writes and
resolve the conflict. Do not create a second project as a workaround.
