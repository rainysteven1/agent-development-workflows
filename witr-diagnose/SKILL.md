---
name: witr-diagnose
description: Diagnose local or explicitly requested Tailscale-host port conflicts and process ancestry with witr. Use when asked what occupies a port, why a process is running, or to trace a PID, name, file, or container. Do not use for installing witr or changing processes.
---

# Witr Diagnose

Identify the owning process and explain the causal chain that started it. Prefer a concise answer backed by a one-shot `witr` query.

## Safety and target

- Diagnose the current machine unless the user explicitly names a remote host.
- Keep the workflow read-only. Never launch the no-argument TUI or use its Kill, Terminate, Pause, Resume, or Renice actions.
- Start without `sudo`. If access is denied or important details are unavailable, explain the missing visibility and obtain authorization immediately before an elevated retry.
- Never store, request in command output, or embed credentials. Do not use `--env` unless the user explicitly requests environment variables after being warned that they may contain secrets.
- Validate a requested port as an integer from 1 through 65535 before placing it in a command.

## Local diagnosis

Confirm the executable first:

```bash
command -v witr
witr --version
```

For a port conflict, run the short query first:

```bash
witr --port PORT --short
```

Run `witr --port PORT` when the user needs bind addresses, service/container context, warnings, or working-directory details. Use `--json` only when structured output materially helps another tool or script.

For other supported targets, use the narrow corresponding query: `witr --pid PID`, `witr --exact NAME`, `witr --file PATH`, or `witr --container NAME`.

Interpret exit codes correctly: 0 is a clean match, 1 is a successful match with warnings, 2 is not found, 3 is insufficient permission, 4 is invalid or ambiguous input, and 5 is an internal error.

## Tailscale Ubuntu host

Only when the user explicitly requests the Ubuntu Tailscale machine, resolve the online node whose Tailscale `HostName` is exactly `ubuntu`. Require a unique match; do not guess among duplicate or offline nodes. Connect as user `ubuntu` to the resolved Tailscale IP and run the same one-shot read-only command through SSH.

Do not elevate remotely by default. If remote `witr` is absent, report that installation is required rather than downloading or installing it under this skill.

## Result

Report the target host, port or other selector, owning PID and executable, causal ancestry/source, relevant bind exposure, and warnings or uncertainty. Avoid dumping unrelated process metadata.
