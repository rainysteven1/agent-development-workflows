#!/usr/bin/python3
"""Inspect and gracefully release the exact writer of a Codex rollout file."""

from __future__ import annotations

import argparse
import datetime as dt
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time


UUID_RE = re.compile(
    r"(?i)(?<![0-9a-f])"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"(?![0-9a-f])"
)
CODEX_PACKAGE_NAME = "@openai/codex"
CODEX_REPOSITORY_URL = "git+https://github.com/openai/codex.git"


class RecoveryError(Exception):
    """A safe, user-actionable recovery error."""


def codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser().resolve() if configured else Path.home() / ".codex"


def extract_uuid(value: str) -> str:
    candidates = (value, re.sub(r"[\r\n]+", "", value))
    matches = {
        match.group(0).lower()
        for candidate in candidates
        for match in UUID_RE.finditer(candidate)
    }
    if len(matches) != 1:
        raise RecoveryError("expected exactly one Codex session UUID")
    return matches.pop()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_rollout(value: str) -> tuple[str, Path]:
    session_uuid = extract_uuid(value)
    root = codex_home().resolve()
    allowed_roots = [root / "sessions", root / "archived_sessions"]

    candidates = (
        Path(value).expanduser(),
        Path(value.replace("\r", "").replace("\n", "")).expanduser(),
    )
    for candidate in candidates:
        if candidate.is_file():
            resolved = candidate.resolve()
            if resolved.suffix != ".jsonl" or not any(
                is_within(resolved, allowed.resolve()) for allowed in allowed_roots
            ):
                raise RecoveryError(
                    "explicit path is not a rollout JSONL under the Codex session roots"
                )
            return session_uuid, resolved

    matches: list[Path] = []
    for search_root in allowed_roots:
        if search_root.is_dir():
            matches.extend(search_root.glob(f"**/*{session_uuid}.jsonl"))
    unique = sorted(
        {
            resolved
            for match in matches
            for resolved in (match.resolve(),)
            if resolved.suffix == ".jsonl"
            and any(is_within(resolved, allowed.resolve()) for allowed in allowed_roots)
        }
    )
    if not unique:
        raise RecoveryError(f"no local rollout JSONL found for session {session_uuid}")
    if len(unique) != 1:
        rendered = "\n".join(f"  {path}" for path in unique)
        raise RecoveryError(f"session UUID resolves to multiple rollout files:\n{rendered}")
    return session_uuid, unique[0]


def lsof_writers(path: Path) -> dict[int, str]:
    executable = shutil.which("lsof")
    if executable is None:
        raise RecoveryError("lsof is required to inspect an exact rollout writer")
    result = subprocess.run(
        [executable, "-F", "pfa", "--", str(path)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if result.returncode not in (0, 1):
        raise RecoveryError(f"lsof failed with exit code {result.returncode}")
    current_pid: int | None = None
    writers: dict[int, set[str]] = {}
    for line in result.stdout.splitlines():
        if line.startswith("p") and line[1:].isdigit():
            current_pid = int(line[1:])
        elif line.startswith("a") and current_pid is not None:
            access = line[1:].strip()
            if access in {"w", "u"}:
                writers.setdefault(current_pid, set()).add(access)
    return {pid: ",".join(sorted(modes)) for pid, modes in sorted(writers.items())}


def ps_value(pid: int, field: str) -> str:
    result = subprocess.run(
        ["ps", "-o", f"{field}=", "-p", str(pid)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.stdout.strip()


@lru_cache(maxsize=1)
def trusted_codex_executables() -> frozenset[Path]:
    launcher = shutil.which("codex")
    if launcher is None:
        return frozenset()

    resolved_launcher = Path(launcher).resolve()
    package_root: Path | None = None
    for candidate in (resolved_launcher.parent, *resolved_launcher.parents):
        manifest_path = candidate / "package.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, dict):
            continue
        repository = manifest.get("repository")
        binary = manifest.get("bin")
        entrypoint = binary.get("codex") if isinstance(binary, dict) else binary
        if (
            manifest.get("name") == CODEX_PACKAGE_NAME
            and isinstance(repository, dict)
            and repository.get("url") == CODEX_REPOSITORY_URL
            and isinstance(entrypoint, str)
            and (candidate / entrypoint).resolve() == resolved_launcher
        ):
            package_root = candidate
            break
    if package_root is None:
        return frozenset()

    trusted: set[Path] = set()
    native_roots = [package_root]
    for manifest_path in package_root.glob("node_modules/@openai/codex-*/package.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, dict):
            continue
        repository = manifest.get("repository")
        if (
            manifest.get("name") == CODEX_PACKAGE_NAME
            and isinstance(repository, dict)
            and repository.get("url") == CODEX_REPOSITORY_URL
        ):
            native_roots.append(manifest_path.parent)
    for native_root in native_roots:
        for candidate in native_root.glob("vendor/*/bin/codex"):
            resolved = candidate.resolve()
            if resolved.is_file() and os.access(resolved, os.X_OK):
                trusted.add(resolved)
    return frozenset(trusted)


def process_start_token(pid: int) -> str:
    proc_stat = Path(f"/proc/{pid}/stat")
    try:
        raw = proc_stat.read_text()
        fields = raw.rpartition(")")[2].split()
        if len(fields) > 19:
            return fields[19]
    except OSError:
        pass
    return ps_value(pid, "lstart")


def process_info(pid: int, file_access: str) -> dict[str, object]:
    try:
        process_group = os.getpgid(pid)
        session_id = os.getsid(pid)
    except ProcessLookupError as exc:
        raise RecoveryError(f"writer PID {pid} disappeared during inspection") from exc

    try:
        cwd = str(Path(f"/proc/{pid}/cwd").resolve())
    except OSError:
        cwd = "unknown"

    executable = "unknown"
    try:
        executable = str(Path(f"/proc/{pid}/exe").resolve())
    except OSError:
        pass

    return {
        "pid": pid,
        "ppid": int(ps_value(pid, "ppid") or 0),
        "process_group": process_group,
        "session_id": session_id,
        "tty": ps_value(pid, "tty") or "?",
        "state": ps_value(pid, "stat") or "?",
        "elapsed": ps_value(pid, "etime") or "?",
        "started": ps_value(pid, "lstart") or "?",
        "command": ps_value(pid, "comm") or "?",
        "cwd": cwd,
        "executable": executable,
        "file_access": file_access,
        "identity_start": process_start_token(pid),
        "verified_codex": Path(executable) in trusted_codex_executables(),
    }


def ancestor_pids() -> set[int]:
    ancestors: set[int] = set()
    current = os.getpid()
    while current > 1 and current not in ancestors:
        ancestors.add(current)
        parent = ps_value(current, "ppid")
        if not parent.isdigit():
            break
        current = int(parent)
    return ancestors


def snapshot(value: str) -> dict[str, object]:
    session_uuid, path = resolve_rollout(value)
    stat = path.stat()
    modified = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc)
    now = dt.datetime.now(tz=dt.timezone.utc)
    writers = lsof_writers(path)
    holders = [process_info(pid, access) for pid, access in writers.items()]
    return {
        "session_uuid": session_uuid,
        "rollout": str(path),
        "size_bytes": stat.st_size,
        "last_write_utc": modified.isoformat(),
        "seconds_since_last_write": max(0, int((now - modified).total_seconds())),
        "status": "occupied" if holders else "unoccupied",
        "holders": holders,
    }


def render(report: dict[str, object]) -> None:
    print(f"session_uuid: {report['session_uuid']}")
    print(f"rollout: {report['rollout']}")
    print(f"status: {report['status']}")
    print(f"last_write_utc: {report['last_write_utc']}")
    print(f"seconds_since_last_write: {report['seconds_since_last_write']}")
    holders = report["holders"]
    if not isinstance(holders, list) or not holders:
        return
    for holder in holders:
        print(
            "holder: "
            f"pid={holder['pid']} ppid={holder['ppid']} "
            f"pgid={holder['process_group']} sid={holder['session_id']} "
            f"tty={holder['tty']} state={holder['state']} "
            f"elapsed={holder['elapsed']} access={holder['file_access']} "
            f"verified_codex={holder['verified_codex']}"
        )
        print(f"holder_started: {holder['started']}")
        print(f"holder_cwd: {holder['cwd']}")
        print(f"holder_executable: {holder['executable']}")


def emit(report: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        render(report)


def bounded_wait(value: str) -> float:
    wait = float(value)
    if not 0.1 <= wait <= 30.0:
        raise argparse.ArgumentTypeError("wait must be between 0.1 and 30 seconds")
    return wait


def open_pidfd(pid: int) -> int:
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise RecoveryError(
            "safe release requires pidfd support; run this helper with /usr/bin/python3"
        )
    try:
        return os.pidfd_open(pid)
    except ProcessLookupError as exc:
        raise RecoveryError(f"writer PID {pid} exited before signaling") from exc


def release(args: argparse.Namespace) -> int:
    before = snapshot(args.session)
    holders = before["holders"]
    if len(holders) != 1:
        raise RecoveryError(
            f"release requires exactly one writable holder; observed {len(holders)}"
        )
    selected = [holder for holder in holders if holder["pid"] == args.pid]
    if not selected:
        raise RecoveryError(f"PID {args.pid} does not currently hold the exact rollout file")
    holder = selected[0]
    if not holder["verified_codex"]:
        raise RecoveryError(f"PID {args.pid} is not verified as a Codex process")
    if args.pid in ancestor_pids():
        raise RecoveryError(f"refusing to signal ancestor PID {args.pid}")
    if not args.yes:
        emit(before, args.json)
        raise RecoveryError("release requires --yes after reviewing the exact holder")

    rollout = Path(str(before["rollout"]))
    pidfd = open_pidfd(args.pid)
    try:
        current_writers = lsof_writers(rollout)
        if current_writers != {args.pid: holder["file_access"]}:
            raise RecoveryError("writable-holder set changed before signaling; inspect again")
        current = process_info(args.pid, current_writers[args.pid])
        immutable_fields = ("identity_start", "executable", "file_access")
        if not current["verified_codex"] or any(
            current[field] != holder[field] for field in immutable_fields
        ):
            raise RecoveryError(f"writer PID {args.pid} changed identity before signaling")

        signal.pidfd_send_signal(pidfd, signal.SIGINT)
    finally:
        os.close(pidfd)
    deadline = time.monotonic() + args.wait
    while time.monotonic() < deadline:
        if not lsof_writers(rollout):
            break
        time.sleep(0.25)

    after = snapshot(args.session)
    emit(after, args.json)
    if after["status"] != "unoccupied":
        print(
            "graceful SIGINT did not release the rollout; re-inspect before escalation",
            file=sys.stderr,
        )
        return 4
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect or gracefully release the exact writer of a Codex rollout file."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("inspect", "verify"):
        child = subparsers.add_parser(command)
        child.add_argument("session", help="session UUID or exact rollout JSONL path")
        child.add_argument("--json", action="store_true", help="emit machine-readable output")

    release_parser = subparsers.add_parser("release")
    release_parser.add_argument("session", help="session UUID or exact rollout JSONL path")
    release_parser.add_argument("--pid", type=int, required=True, help="exact current writer PID")
    release_parser.add_argument(
        "--wait", type=bounded_wait, default=8.0, help="bounded SIGINT wait (0.1-30 seconds)"
    )
    release_parser.add_argument("--yes", action="store_true", help="confirm graceful release")
    release_parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "release":
            return release(args)
        report = snapshot(args.session)
        emit(report, args.json)
        if args.command == "verify" and report["status"] != "unoccupied":
            return 4
        return 0
    except RecoveryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
