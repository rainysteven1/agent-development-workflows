---
name: memory-governance
description: "Govern persistent Agent Memory reads, capture, promotion, sharing, conflicts, revocation, and expiry. Use when TencentDB Agent Memory, Chat Memory, reusable Memory Skills, team sharing, or cross-session preferences are involved. Do not use Memory as proof of current code or runtime state."
---

# Memory Governance

Use persistent Memory as reviewed experience, not as a primary code, runtime,
or policy authority. This skill owns Memory lifecycle and trust boundaries; it
does not replace `$repo-evidence`, Git, tests, observed runtime, or approved
team documentation.

## Enabled scope

For Codex Builder workspace domains, only Chat Memory and reviewed Memory Skills are
enabled. Tencent Wiki and CodeGraph are disabled. Do not attempt to create,
query, bind, or promote disabled asset types.

Map one Plane workspace to one Memory Team. Use `surveying-memory` for Team
`Surveying` and `platform-memory` for Team `Platform`; both select Agent `Codex
Builder`. Use the Plane WP or Issue identifier as the Memory task ID when one
exists, and `no-task` otherwise. Machines are credential boundaries, not Memory
Team boundaries. See [references/surveying-memory.md](references/surveying-memory.md).

## Read discipline

- Record asset type, owner, visibility, source references, review time, expiry,
  scope, and confidence when available.
- Private Memory may suggest preferences, incidents, terminology, and candidate
  procedures. Team Memory is a reviewed hint, not a mandatory rule.
- Revalidate repository claims with current Git/source/tests and runtime claims
  with live observations.
- When Memory conflicts with its cited source or current evidence, mark it stale
  or contested and use the authoritative source. Do not silently choose Memory.

## Write and promotion discipline

Automatic capture remains private. Nothing is promoted to Team Memory
automatically. A Team record requires an owner, reviewer, source references,
scope, confidence, review time, expiry, and supersession metadata.

Never store raw secrets, credentials, private keys, full chat transcripts,
current function signatures, complete source files, or complete copies of team
documents.

Promote durable knowledge to its real authority first:

- reusable execution procedure -> reviewed Git Skill
- mandatory repository behavior -> closest `AGENTS.md`, maintained script, or test
- formal architecture or operating decision -> approved team documentation
- one-off experience -> Private Memory
- repeated reviewed experience -> Team Memory

After promotion, Memory keeps only a bounded pointer, rationale, provenance, and
expiry. Team sharing, revocation, deletion, ACL changes, and promotion are
external writes and require explicit user authorization plus read-after-write
verification.

## Credentials and transport

Never print, paste, clone an existing host key, or put a Memory user key in TOML,
Git, logs, or a prompt. Provision a new destination-specific key through the
maintained authority, deliver it once over an authenticated channel, verify its
principal and mode-600 destination file, then remove every transfer copy. The
Codex provider obtains its bearer token through the bundled command helper. MCP
or an LLM proxy is transport; transport does not make returned content
authoritative.

## Report

State which Memory asset influenced the task, whether it was private or shared,
what source verified it, any conflict or expiry, and every external Memory write
that was actually performed.
