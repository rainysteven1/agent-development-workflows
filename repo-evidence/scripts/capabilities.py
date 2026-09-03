#!/usr/bin/env python3
"""Read-only inventory of repository evidence tools and index readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any


def run(command: list[str], cwd: Path, timeout: int = 30) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "exitCode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"exitCode": 124, "stdout": "", "stderr": "timeout"}


def version(command: str, cwd: Path) -> dict[str, Any]:
    resolved = shutil.which(command)
    if not resolved:
        return {"installed": False}
    result = run([resolved, "--version"], cwd)
    output = (result["stdout"] or result["stderr"]).strip().splitlines()
    return {
        "installed": True,
        "path": resolved,
        "version": output[0] if output else "unknown",
        "versionExitCode": result["exitCode"],
    }


def parse_graft(repo: Path) -> dict[str, Any]:
    state = version("graft", repo)
    if not state["installed"]:
        return state
    result = run([state["path"], "check", "--json"], repo, timeout=60)
    raw = result["stdout"]
    start = raw.find("{")
    try:
        payload = json.loads(raw[start:]) if start >= 0 else {}
    except json.JSONDecodeError:
        payload = {}
    context = payload.get("context") or {}
    graph = payload.get("graph") or {}
    state.update(
        {
            "checkExitCode": result["exitCode"],
            "structuralReady": graph.get("ok") is True,
            "contextReady": context.get("ok") is True,
            "contextMissing": context.get("missing"),
            "nodes": graph.get("nodes"),
            "pending": graph.get("pending"),
            "added": len(graph.get("added") or []),
            "changed": len(graph.get("changed") or []),
            "stale": len(graph.get("stale") or []),
        }
    )
    return state


def match_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, re.MULTILINE)
    return int(match.group(1).replace(",", "")) if match else None


def parse_zg(repo: Path) -> dict[str, Any]:
    state = version("zg", repo)
    if not state["installed"]:
        return state
    result = run(
        [state["path"], "status", str(repo), "--mode", "direct", "--check-ready"],
        repo,
        timeout=60,
    )
    output = result["stdout"]
    embedding = re.search(r"^\s*Embedding\s+(.+)$", output, re.MULTILINE)
    state.update(
        {
            "statusExitCode": result["exitCode"],
            "ready": result["exitCode"] == 0,
            "indexedFiles": match_int(r"/\s*([\d,]+)\s+files", output),
            "entities": match_int(r"^\s*Entities\s+([\d,]+)", output),
            "pending": match_int(r"^\s*Queue\s+([\d,]+)\s+pending", output),
            "failed": match_int(r"pending\s+[^\n]*?([\d,]+)\s+failed", output),
            "embedding": embedding.group(1).strip() if embedding else None,
        }
    )
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    requested = args.repo.resolve()
    root_result = run(["git", "rev-parse", "--show-toplevel"], requested)
    if root_result["exitCode"] != 0:
        raise SystemExit("--repo must be inside a Git worktree")
    repo = Path(root_result["stdout"].strip()).resolve()
    head = run(["git", "rev-parse", "HEAD"], repo)["stdout"].strip()
    status = run(["git", "status", "--porcelain=v1"], repo)["stdout"]
    payload = {
        "format": "repo-evidence-capabilities/v1",
        "repository": str(repo),
        "head": head,
        "dirty": bool(status.strip()),
        "tools": {
            "fastctx": version("fastctx", repo),
            "graft": parse_graft(repo),
            "zg": parse_zg(repo),
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
