---
name: codex-session-writer-recovery
description: Diagnose and safely recover local Codex sessions that fail to resume with "already has an active writer" or code -32600. Use for an exact local session UUID or rollout JSONL; do not use for general database corruption, missing sessions, or remote-only thread ownership.
---

# Codex Session Writer Recovery

Recover the session without deleting its rollout, editing Codex state databases, or stopping unrelated Codex processes.

## Safety Contract

- Treat the rollout JSONL and state database as durable user data. Never delete, truncate, rename, patch, or recreate them to clear a writer conflict.
- Resolve exactly one session UUID and one rollout path before signaling a process. A pasted path may wrap across lines; prefer the UUID embedded in the error.
- Inventory open file descriptors before mutation. Never use `pkill`, `killall`, a process-name glob, or a broad process sweep.
- Signal only the single process that currently holds a writable FD for the exact rollout and whose executable is verified as Codex. Protect the agent ancestry; never signal the writer's whole process group.
- Use graceful `SIGINT` first. Do not escalate to `SIGTERM` or `SIGKILL` automatically. A failed graceful exit requires fresh observation and new user authorization for escalation.
- A request to fix this exact resume error authorizes graceful closure of the exact blocking Codex writer. It does not authorize stopping other sessions, app servers, or terminal processes.

## Workflow

1. Extract the session UUID or exact JSONL path from the error. Record the requested session as the only target.
2. Check the installed interface with `codex resume --help`. Do not update Codex merely to clear a writer conflict.
3. Run the helper from this skill directory:

   ```bash
   /usr/bin/python3 scripts/session_writer.py inspect SESSION_UUID_OR_PATH
   ```

4. Classify the result:
   - `unoccupied`: do not mutate anything. Run health checks and let the user retry.
   - One exact Codex holder: compare its PID, writable FD mode, process group, terminal, elapsed time, executable, rollout last-write time, and working directory. If the user asked to resolve this conflict, release that exact writer PID gracefully.
   - Multiple holders or an unverified process: stop and identify the intended PID with the user. Do not guess.
   - No local rollout match: stop. This skill does not repair missing files or remote app-server ownership.
5. Release only the selected current holder:

   ```bash
   /usr/bin/python3 scripts/session_writer.py release SESSION_UUID_OR_PATH --pid PID --yes
   ```

6. After any interruption or uncertain signal, rerun `inspect` before doing anything else. The helper is safe to rerun.
7. Verify both the lock boundary and Codex state:

   ```bash
   /usr/bin/python3 scripts/session_writer.py verify SESSION_UUID_OR_PATH
   codex doctor --summary --no-color --ascii
   ```

   Require `verify` to report `unoccupied`; require `codex doctor` to report healthy state databases and matching thread inventory. Report unrelated doctor notes separately.
8. Return the exact `codex resume SESSION_UUID` command to the user.

## Interactive Verification Trap

Do not launch `codex resume` in an unattended test merely to prove bootstrap. That test becomes the new active writer and can survive an interrupted agent turn. Prefer `verify` plus `codex doctor`; let the user resume in their terminal. If an interactive test is explicitly required, keep its process handle, exit it in the same control flow, and always run `verify` afterward.

## Failure Handling

- If `SIGINT` does not release the file within the helper's bounded wait, report the surviving PID/process group and rerun `inspect`. Ask before any stronger signal.
- Release requires Linux `pidfd` support so the signal remains bound to the revalidated process identity. On another platform, use the helper for inspection only and stop before mutation.
- If the file becomes occupied again, identify the new PID. Do not assume the original process restarted.
- If the error persists while `verify` says `unoccupied`, collect a redacted `codex doctor --json` report and the installed Codex version. Treat remote ownership or a Codex defect as a hypothesis; do not alter local state without evidence.
