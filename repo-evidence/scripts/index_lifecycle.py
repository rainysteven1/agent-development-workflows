#!/usr/bin/env python3
"""Manage canonical repository indexes and task-worktree Graft snapshots."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any


SCHEMA_VERSION = 1
STATE_DIR_NAME = "repo-evidence"
CONFIG_NAME = "index-lifecycle.json"
STATE_NAME = "index-state.json"
LOCK_NAME = "index-lifecycle.lock"
OWNERSHIP_NAME = ".repo-evidence-managed.json"
HOOK_MARKER = "# repo-evidence:index-lifecycle:v1"
HOOK_EVENTS = ("post-checkout", "post-merge", "post-rewrite")
DEFAULT_EMBEDDING = "local/potion-code-16m-v2"
COMMAND_TIMEOUT_SECONDS = 600
LOCK_TIMEOUT_SECONDS = 30


class LifecycleError(RuntimeError):
    pass


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def run(
    command: list[str], cwd: Path, *, timeout: int = COMMAND_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as error:
        raise LifecycleError(f"required command is not installed: {command[0]}") from error
    except subprocess.TimeoutExpired as error:
        raise LifecycleError(
            f"command timed out after {timeout}s: {shlex.join(command)}"
        ) from error


def command_summary(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stdout = result.stdout.encode("utf-8")
    stderr = result.stderr.encode("utf-8")
    return {
        "exitCode": result.returncode,
        "stdoutBytes": len(stdout),
        "stdoutSha256": hashlib.sha256(stdout).hexdigest(),
        "stderrBytes": len(stderr),
        "stderrSha256": hashlib.sha256(stderr).hexdigest(),
    }


def graft_check_ready(result: subprocess.CompletedProcess[str]) -> bool:
    if result.returncode != 0:
        return False
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    graph = payload.get("graph") if isinstance(payload, dict) else None
    return isinstance(graph, dict) and graph.get("ok") is True


def checked_action(command: list[str], cwd: Path) -> dict[str, Any]:
    result = run(command, cwd)
    if result.returncode != 0:
        raise LifecycleError(
            f"command failed ({result.returncode}): {shlex.join(command)}; "
            f"stderr_sha256={hashlib.sha256(result.stderr.encode('utf-8')).hexdigest()}"
        )
    if command[:2] == ["graft", "check"] and not graft_check_ready(result):
        raise LifecycleError("Graft check did not return graph.ok=true JSON")
    return command_summary(result)


def git(repo: Path, *arguments: str) -> str:
    result = run(["git", "-C", str(repo), *arguments], repo, timeout=60)
    if result.returncode != 0:
        raise LifecycleError(
            f"Git command failed for {repo}: git {' '.join(arguments)}"
        )
    return result.stdout.strip()


def git_optional(repo: Path, *arguments: str) -> str | None:
    result = run(["git", "-C", str(repo), *arguments], repo, timeout=60)
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        raise LifecycleError(
            f"Git command failed for {repo}: git {' '.join(arguments)}"
        )
    return result.stdout.strip()


def git_is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        repo,
        timeout=60,
    )
    if result.returncode not in {0, 1}:
        raise LifecycleError("cannot verify task ancestry against the canonical baseline")
    return result.returncode == 0


def repository_context(path: Path) -> dict[str, Any]:
    requested = path.resolve()
    root = Path(git(requested, "rev-parse", "--show-toplevel")).resolve()
    common_value = Path(git(root, "rev-parse", "--git-common-dir"))
    common_dir = (
        (root / common_value).resolve()
        if not common_value.is_absolute()
        else common_value.resolve()
    )
    head = git(root, "rev-parse", "HEAD").lower()
    branch = git(root, "branch", "--show-current")
    return {
        "root": root,
        "commonDir": common_dir,
        "head": head,
        "branch": branch,
        "dirty": bool(git(root, "status", "--porcelain=v1")),
    }


def metadata_paths(common_dir: Path) -> dict[str, Path]:
    state_dir = common_dir / STATE_DIR_NAME
    return {
        "directory": state_dir,
        "config": state_dir / CONFIG_NAME,
        "state": state_dir / STATE_NAME,
        "lock": state_dir / LOCK_NAME,
    }


def resolve_hooks_dir(repository: Path, common_dir: Path) -> Path:
    configured = git_optional(
        repository, "config", "--path", "--get", "core.hooksPath"
    )
    if configured is None:
        return common_dir / "hooks"
    path = Path(configured)
    if not path.is_absolute():
        raise LifecycleError("relative core.hooksPath is unsupported for shared worktree hooks")
    return path.resolve()


def load_json(path: Path, *, required: bool) -> dict[str, Any]:
    if not path.is_file():
        if required:
            raise LifecycleError(f"managed index configuration is missing: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LifecycleError(f"cannot load JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise LifecycleError(f"{path} must contain a JSON object")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def ownership_payload(task: Path, common_dir: Path) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "taskWorktree": str(task.resolve()),
        "gitCommonDir": str(common_dir.resolve()),
    }


def task_cache_owned(task: Path, common_dir: Path) -> bool:
    marker = task / "graft" / OWNERSHIP_NAME
    if not marker.is_file() or marker.is_symlink():
        return False
    return load_json(marker, required=True) == ownership_payload(task, common_dir)


def claim_task_cache(task: Path, common_dir: Path) -> None:
    graft = task / "graft"
    if graft.is_symlink() or (graft.exists() and not graft.is_dir()):
        raise LifecycleError(f"refusing a symlinked or invalid task cache path: {graft}")
    graft.mkdir(parents=True, exist_ok=True)
    marker = graft / OWNERSHIP_NAME
    if marker.exists() and not task_cache_owned(task, common_dir):
        raise LifecycleError(f"task cache has a conflicting ownership marker: {marker}")
    atomic_write_json(marker, ownership_payload(task, common_dir))


def tool_version(command: str, cwd: Path) -> str:
    resolved = shutil.which(command)
    if not resolved:
        raise LifecycleError(f"required command is not installed: {command}")
    result = run([resolved, "--version"], cwd, timeout=60)
    if result.returncode != 0 or not result.stdout.strip():
        raise LifecycleError(f"cannot resolve {command} version")
    return result.stdout.strip().splitlines()[0]


def validate_config(config: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if config.get("schemaVersion") != SCHEMA_VERSION:
        raise LifecycleError("managed index configuration has an unsupported schemaVersion")
    canonical = Path(str(config.get("canonicalWorktree", ""))).resolve()
    canonical_context = repository_context(canonical)
    if canonical_context["commonDir"] != context["commonDir"]:
        raise LifecycleError("canonical and requested worktrees do not share a Git common directory")
    target_branch = str(config.get("targetBranch", ""))
    if not target_branch:
        raise LifecycleError("managed index configuration has no targetBranch")
    if config.get("graftVersion") != tool_version("graft", canonical):
        raise LifecycleError("Graft version changed; revalidate snapshot compatibility explicitly")
    if config.get("zgVersion") != tool_version("zg", canonical):
        raise LifecycleError("Zvec-Grep version changed; reconfigure the managed baseline explicitly")
    if config.get("hooksPath") != str(
        resolve_hooks_dir(canonical, canonical_context["commonDir"])
    ):
        raise LifecycleError("active Git hooks path changed; reconfigure lifecycle hooks explicitly")
    return {**config, "canonicalWorktree": str(canonical)}


def require_clean(context: dict[str, Any], label: str) -> None:
    if context["dirty"]:
        raise LifecycleError(f"{label} worktree must be clean")


def hook_content(event: str) -> str:
    python = shlex.quote(sys.executable)
    script = shlex.quote(str(Path(__file__).resolve()))
    return (
        "#!/bin/sh\n"
        f"{HOOK_MARKER}\n"
        f"{python} {script} hook --repo \"$PWD\" --event {event} || "
        f"printf '%s\\n' 'repo-evidence: {event} index maintenance failed; inspect status before relying on indexes' >&2\n"
        "exit 0\n"
    )


def hook_actions(hooks_dir: Path) -> list[dict[str, str]]:
    actions = []
    for event in HOOK_EVENTS:
        path = hooks_dir / event
        expected = hook_content(event)
        if path.is_symlink():
            raise LifecycleError(f"refusing symlinked Git hook path: {path}")
        if path.exists():
            if not path.is_file():
                raise LifecycleError(f"refusing non-file Git hook path: {path}")
            current = path.read_text(encoding="utf-8")
            if not current.startswith(f"#!/bin/sh\n{HOOK_MARKER}\n"):
                raise LifecycleError(f"refusing to overwrite existing Git hook: {path}")
            if current == expected:
                continue
        actions.append({"event": event, "path": str(path), "action": "write"})
    return actions


def atomic_write_hook(path: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o755)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def install_hooks(
    hooks_dir: Path, repository: Path, common_dir: Path
) -> list[dict[str, str]]:
    actions = hook_actions(hooks_dir)
    if resolve_hooks_dir(repository, common_dir) != hooks_dir:
        raise LifecycleError("active Git hooks path changed before installation")
    hooks_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
    previous = {
        Path(action["path"]): (
            (
                Path(action["path"]).read_bytes(),
                stat.S_IMODE(Path(action["path"]).stat().st_mode),
            )
            if Path(action["path"]).is_file()
            else None
        )
        for action in actions
    }
    try:
        for action in actions:
            if resolve_hooks_dir(repository, common_dir) != hooks_dir:
                raise LifecycleError("active Git hooks path changed before hook write")
            path = Path(action["path"])
            atomic_write_hook(path, hook_content(action["event"]))
            if resolve_hooks_dir(repository, common_dir) != hooks_dir:
                raise LifecycleError("active Git hooks path changed after hook write")
    except (LifecycleError, OSError):
        for path, content in previous.items():
            if content is None:
                marker = f"#!/bin/sh\n{HOOK_MARKER}\n".encode("utf-8")
                if path.is_file() and path.read_bytes().startswith(marker):
                    path.unlink()
            else:
                previous_bytes, previous_mode = content
                path.write_bytes(previous_bytes)
                path.chmod(previous_mode)
        raise
    return actions


def desired_config(
    context: dict[str, Any], branch: str, bootstrap_indexes: bool
) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "canonicalWorktree": str(context["root"]),
        "targetBranch": branch,
        "bootstrapAuthorized": bootstrap_indexes,
        "graftVersion": tool_version("graft", context["root"]),
        "zgVersion": tool_version("zg", context["root"]),
        "zgEmbedding": DEFAULT_EMBEDDING,
        "zgDevice": "cpu",
        "hooksPath": str(resolve_hooks_dir(context["root"], context["commonDir"])),
    }


def configure(
    repo: Path,
    *,
    target_branch: str | None,
    bootstrap_indexes: bool,
    apply: bool,
) -> dict[str, Any]:
    context = repository_context(repo)
    require_clean(context, "canonical")
    branch = target_branch or context["branch"]
    if not branch:
        raise LifecycleError("canonical worktree must be on a named target branch")
    config = desired_config(context, branch, bootstrap_indexes)
    paths = metadata_paths(context["commonDir"])
    current = load_json(paths["config"], required=False)
    if current and current != config:
        raise LifecycleError(
            "managed index configuration already exists with different values"
        )
    hooks_dir = Path(config["hooksPath"])
    hooks = hook_actions(hooks_dir)
    convergence_actions(context["root"], config)
    result = {
        "action": None if current == config and not hooks else "configure",
        "applied": apply,
        "canonicalWorktree": str(context["root"]),
        "commonDir": str(context["commonDir"]),
        "targetBranch": branch,
        "bootstrapAuthorized": bootstrap_indexes,
        "hooks": hooks,
    }
    if apply:
        with state_lock(paths["lock"]):
            context = repository_context(context["root"])
            require_clean(context, "canonical")
            branch = target_branch or context["branch"]
            if not branch:
                raise LifecycleError("canonical worktree must be on a named target branch")
            config = desired_config(context, branch, bootstrap_indexes)
            hooks_dir = Path(config["hooksPath"])
            current = load_json(paths["config"], required=False)
            if current and current != config:
                raise LifecycleError("managed index configuration changed before apply")
            hooks = hook_actions(hooks_dir)
            convergence_actions(context["root"], config)
            installed_hooks = install_hooks(
                hooks_dir, context["root"], context["commonDir"]
            )
            atomic_write_json(paths["config"], config)
            result.update(
                {
                    "action": None if current == config and not hooks else "configure",
                    "canonicalWorktree": str(context["root"]),
                    "commonDir": str(context["commonDir"]),
                    "targetBranch": branch,
                    "hooks": installed_hooks,
                }
            )
        result["convergence"] = converge(context["root"], apply=True)
        result["verified"] = result["convergence"]["status"] in {"ready", "already-ready"}
    else:
        result["verified"] = current == config and not hooks
    return result


@contextmanager
def state_lock(path: Path):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise LifecycleError(
                        f"index lifecycle lock stayed busy for {LOCK_TIMEOUT_SECONDS}s"
                    )
                time.sleep(0.1)
        yield handle
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def convergence_actions(canonical: Path, config: dict[str, Any]) -> list[list[str]]:
    if not (canonical / "graft").is_dir() and config.get("bootstrapAuthorized") is not True:
        raise LifecycleError("canonical Graft index is missing and bootstrap is not authorized")
    actions = [
        ["graft", "build", str(canonical), "--no-gitignore", "--no-ignore"],
        ["graft", "check", str(canonical), "--json"],
    ]
    if (canonical / ".zvec-grep").is_dir():
        actions.append(["zg", "index", str(canonical), "--mode", "direct"])
    elif config.get("bootstrapAuthorized") is True:
        actions.append(
            [
                "zg",
                "index",
                str(canonical),
                "--embedding",
                str(config["zgEmbedding"]),
                "--device",
                str(config["zgDevice"]),
                "--mode",
                "direct",
            ]
        )
    else:
        raise LifecycleError("canonical Zvec-Grep index is missing and bootstrap is not authorized")
    actions.append(["zg", "status", str(canonical), "--mode", "direct", "--check-ready"])
    return actions


def verify_ready(canonical: Path) -> list[dict[str, Any]] | None:
    if not (canonical / "graft").is_dir() or not (canonical / ".zvec-grep").is_dir():
        return None
    commands = [
        ["graft", "check", str(canonical), "--json"],
        ["zg", "status", str(canonical), "--mode", "direct", "--check-ready"],
    ]
    evidence = []
    for command in commands:
        result = run(command, canonical)
        evidence.append({"command": command, **command_summary(result)})
        if command[:2] == ["graft", "check"]:
            if not graft_check_ready(result):
                return None
        elif result.returncode != 0:
            return None
    return evidence


def converge(repo: Path, *, apply: bool) -> dict[str, Any]:
    context = repository_context(repo)
    paths = metadata_paths(context["commonDir"])
    config = validate_config(load_json(paths["config"], required=True), context)
    canonical = Path(config["canonicalWorktree"])
    if context["root"] != canonical:
        raise LifecycleError("canonical convergence must run from the configured canonical worktree")
    if context["branch"] != config["targetBranch"]:
        raise LifecycleError("canonical worktree is not on its configured target branch")
    require_clean(context, "canonical")
    state = load_json(paths["state"], required=False)
    current = state.get("canonical") if isinstance(state.get("canonical"), dict) else {}
    ready_evidence = None
    if current.get("revision") == context["head"] and current.get("status") == "ready":
        ready_evidence = verify_ready(canonical)
    if ready_evidence is not None:
        return {
            "status": "already-ready",
            "revision": context["head"],
            "applied": apply,
            "actions": [],
            "evidence": ready_evidence,
        }
    actions = convergence_actions(canonical, config)
    result = {
        "status": "would-converge",
        "revision": context["head"],
        "applied": apply,
        "actions": actions,
    }
    if not apply:
        return result
    with state_lock(paths["lock"]):
        state = load_json(paths["state"], required=False)
        current = state.get("canonical") if isinstance(state.get("canonical"), dict) else {}
        ready_evidence = None
        if current.get("revision") == context["head"] and current.get("status") == "ready":
            ready_evidence = verify_ready(canonical)
        if ready_evidence is not None:
            return {
                "status": "already-ready",
                "revision": context["head"],
                "applied": True,
                "actions": [],
                "evidence": ready_evidence,
            }
        evidence = []
        for command in actions:
            evidence.append({"command": command, **checked_action(command, canonical)})
        final_context = repository_context(canonical)
        require_clean(final_context, "canonical after index convergence")
        if final_context["head"] != context["head"]:
            raise LifecycleError("canonical HEAD changed during index convergence")
        state.update(
            {
                "schemaVersion": SCHEMA_VERSION,
                "canonical": {
                    "revision": context["head"],
                    "status": "ready",
                    "completedAt": int(time.time()),
                    "evidence": evidence,
                },
            }
        )
        state.setdefault("tasks", {})
        atomic_write_json(paths["state"], state)
    return {**result, "status": "ready", "evidence": evidence}


def snapshot_actions(
    canonical: Path,
    task: Path,
    *,
    copy_snapshot: bool,
    allow_existing: bool,
) -> list[list[str]]:
    if copy_snapshot and not (canonical / "graft").is_dir():
        raise LifecycleError("canonical Graft snapshot is missing")
    actions = []
    for name in ("graft", ".graft"):
        destination = task / name
        if destination.is_symlink():
            raise LifecycleError("refusing a symlinked Graft snapshot")
        if destination.exists() and not allow_existing:
            raise LifecycleError(f"task cache is not managed by this lifecycle: {destination}")
        if destination.exists() and not destination.is_dir():
            raise LifecycleError(f"task cache path is not a directory: {destination}")
    if copy_snapshot:
        for name in ("graft", ".graft"):
            source = canonical / name
            destination = task / name
            if not source.exists():
                continue
            if source.is_symlink() or destination.is_symlink():
                raise LifecycleError("refusing a symlinked Graft snapshot")
            if destination.exists():
                if not destination.is_dir():
                    raise LifecycleError(f"task cache path is not a directory: {destination}")
                if any(destination.iterdir()):
                    continue
            actions.append(
                ["rsync", "-a", "--safe-links", f"{source}/", f"{destination}/"]
            )
    actions.extend(
        [
            ["graft", "build", str(task), "--no-gitignore", "--no-ignore"],
            ["graft", "check", str(task), "--json"],
        ]
    )
    return actions


def task_plan(
    context: dict[str, Any], paths: dict[str, Path], config: dict[str, Any]
) -> dict[str, Any]:
    canonical = Path(config["canonicalWorktree"])
    canonical_context = repository_context(canonical)
    require_clean(canonical_context, "canonical")
    state = load_json(paths["state"], required=True)
    baseline = state.get("canonical")
    if not isinstance(baseline, dict) or baseline.get("status") != "ready":
        raise LifecycleError("canonical index baseline is not ready")
    if baseline.get("revision") != canonical_context["head"]:
        raise LifecycleError("canonical index baseline does not match canonical HEAD")
    if verify_ready(canonical) is None:
        raise LifecycleError("canonical index baseline no longer passes readiness checks")
    if (context["root"] / ".zvec-grep").exists():
        raise LifecycleError("task worktree unexpectedly contains a copied Zvec-Grep index")
    tasks = state.get("tasks")
    if tasks is None:
        tasks = {}
    if not isinstance(tasks, dict):
        raise LifecycleError("managed index task state is malformed")
    existing = tasks.get(str(context["root"]))
    allow_existing = isinstance(existing, dict) and task_cache_owned(
        context["root"], context["commonDir"]
    )
    copy_snapshot = git_is_ancestor(
        context["root"], baseline["revision"], context["head"]
    )
    actions = snapshot_actions(
        canonical,
        context["root"],
        copy_snapshot=copy_snapshot,
        allow_existing=allow_existing,
    )
    return {
        "state": state,
        "baseline": baseline,
        "actions": actions,
        "snapshotCopied": any(command[0] == "rsync" for command in actions),
    }


def prepare_worktree(repo: Path, *, apply: bool) -> dict[str, Any]:
    context = repository_context(repo)
    paths = metadata_paths(context["commonDir"])
    config = validate_config(load_json(paths["config"], required=True), context)
    canonical = Path(config["canonicalWorktree"])
    if context["root"] == canonical:
        return converge(canonical, apply=apply)
    plan = task_plan(context, paths, config)
    result = {
        "status": "would-prepare",
        "applied": apply,
        "taskWorktree": str(context["root"]),
        "taskRevision": context["head"],
        "baselineRevision": plan["baseline"]["revision"],
        "actions": plan["actions"],
        "snapshotCopied": plan["snapshotCopied"],
        "zvecCopied": False,
    }
    if not apply:
        return result
    with state_lock(paths["lock"]):
        context = repository_context(context["root"])
        config = validate_config(load_json(paths["config"], required=True), context)
        plan = task_plan(context, paths, config)
        state = plan["state"]
        tasks = state.setdefault("tasks", {})
        tasks[str(context["root"])] = {
            "revision": context["head"],
            "baselineRevision": plan["baseline"]["revision"],
            "status": "preparing",
            "snapshotCopied": plan["snapshotCopied"],
            "startedAt": int(time.time()),
        }
        atomic_write_json(paths["state"], state)
        claim_task_cache(context["root"], context["commonDir"])
        evidence = []
        for command in plan["actions"]:
            evidence.append(
                {"command": command, **checked_action(command, context["root"])}
            )
        final_context = repository_context(context["root"])
        if final_context["head"] != context["head"]:
            raise LifecycleError("task HEAD changed during snapshot preparation")
        if (context["root"] / ".zvec-grep").exists():
            raise LifecycleError("task preparation created a forbidden Zvec-Grep copy")
        if not task_cache_owned(context["root"], context["commonDir"]):
            raise LifecycleError("task Graft ownership marker was not preserved")
        tasks[str(context["root"])] = {
            "revision": context["head"],
            "baselineRevision": plan["baseline"]["revision"],
            "status": "ready",
            "snapshotCopied": plan["snapshotCopied"],
            "completedAt": int(time.time()),
            "evidence": evidence,
        }
        atomic_write_json(paths["state"], state)
    return {
        **result,
        "status": "ready",
        "taskRevision": context["head"],
        "baselineRevision": plan["baseline"]["revision"],
        "actions": plan["actions"],
        "snapshotCopied": plan["snapshotCopied"],
        "evidence": evidence,
    }


def inspect_status(repo: Path) -> dict[str, Any]:
    context = repository_context(repo)
    paths = metadata_paths(context["commonDir"])
    config = validate_config(load_json(paths["config"], required=True), context)
    state = load_json(paths["state"], required=False)
    return {
        "repository": str(context["root"]),
        "head": context["head"],
        "branch": context["branch"],
        "commonDir": str(context["commonDir"]),
        "canonicalWorktree": config["canonicalWorktree"],
        "canonical": state.get("canonical"),
        "task": (state.get("tasks") or {}).get(str(context["root"])),
    }


def handle_hook(repo: Path, event: str) -> dict[str, Any]:
    if event not in HOOK_EVENTS:
        raise LifecycleError(f"unsupported hook event: {event}")
    context = repository_context(repo)
    config = validate_config(
        load_json(metadata_paths(context["commonDir"])["config"], required=True),
        context,
    )
    if context["root"] == Path(config["canonicalWorktree"]):
        if context["branch"] != config["targetBranch"]:
            return {"status": "skipped-non-target", "event": event}
        result = converge(context["root"], apply=True)
    else:
        result = prepare_worktree(context["root"], apply=True)
    return {"event": event, **result}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    configure_parser = commands.add_parser("configure")
    configure_parser.add_argument("--repo", type=Path, default=Path.cwd())
    configure_parser.add_argument("--target-branch")
    configure_parser.add_argument("--bootstrap-indexes", action="store_true")
    configure_parser.add_argument("--apply", action="store_true")
    for name in ("converge", "prepare-worktree"):
        command = commands.add_parser(name)
        command.add_argument("--repo", type=Path, default=Path.cwd())
        command.add_argument("--apply", action="store_true")
    status = commands.add_parser("status")
    status.add_argument("--repo", type=Path, default=Path.cwd())
    hook = commands.add_parser("hook")
    hook.add_argument("--repo", type=Path, default=Path.cwd())
    hook.add_argument("--event", choices=HOOK_EVENTS, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "configure":
            result = configure(
                args.repo,
                target_branch=args.target_branch,
                bootstrap_indexes=args.bootstrap_indexes,
                apply=args.apply,
            )
        elif args.command == "converge":
            result = converge(args.repo, apply=args.apply)
        elif args.command == "prepare-worktree":
            result = prepare_worktree(args.repo, apply=args.apply)
        elif args.command == "status":
            result = inspect_status(args.repo)
        else:
            result = handle_hook(args.repo, args.event)
        emit(result)
        return 0
    except (LifecycleError, OSError) as error:
        emit({"error": str(error), "status": "failed"})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
