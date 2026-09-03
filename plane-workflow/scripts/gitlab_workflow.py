#!/usr/bin/env python3
"""Read immutable GitLab Merge Request state through glab."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


GIT_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


class GitLabWorkflowError(RuntimeError):
    pass


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _run_glab(
    repo: Path,
    arguments: list[str],
) -> Any:
    command = ["glab", *arguments]
    completed = subprocess.run(
        command,
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise GitLabWorkflowError(
            f"glab command failed with exit {completed.returncode}: {detail[:2000]}"
        )
    if not completed.stdout.strip():
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise GitLabWorkflowError("glab did not return JSON") from error


def _validate_repo(repo: Path) -> Path:
    resolved = repo.resolve()
    completed = subprocess.run(
        ["git", "-C", str(resolved), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise GitLabWorkflowError(f"not a Git repository: {resolved}")
    return Path(completed.stdout.strip()).resolve()


def inspect_merge_request(repo: Path, iid: int) -> dict[str, Any]:
    if iid < 1:
        raise GitLabWorkflowError("Merge Request IID must be positive")
    value = _run_glab(repo, ["api", f"projects/:fullpath/merge_requests/{iid}"])
    if not isinstance(value, dict):
        raise GitLabWorkflowError("GitLab Merge Request API returned an unexpected response")
    diff_refs = value.get("diff_refs") if isinstance(value.get("diff_refs"), dict) else {}
    url = str(value.get("web_url") or "").strip()
    state = str(value.get("state") or "").strip()
    base_revision = str(diff_refs.get("base_sha") or "").lower()
    head_revision = str(diff_refs.get("head_sha") or value.get("sha") or "").lower()
    merge_revision = str(value.get("merge_commit_sha") or "").lower() or None
    squash_revision = str(value.get("squash_commit_sha") or "").lower() or None
    if value.get("iid") != iid:
        raise GitLabWorkflowError("GitLab returned a different Merge Request IID")
    if not url.endswith(f"/-/merge_requests/{iid}"):
        raise GitLabWorkflowError("GitLab returned an unexpected Merge Request URL")
    if state not in {"opened", "closed", "merged"}:
        raise GitLabWorkflowError("GitLab returned an unexpected Merge Request state")
    if not GIT_REVISION_RE.fullmatch(base_revision) or not GIT_REVISION_RE.fullmatch(
        head_revision
    ):
        raise GitLabWorkflowError("GitLab Merge Request is missing full base/head revisions")
    for label, revision in (
        ("merge", merge_revision),
        ("squash", squash_revision),
    ):
        if revision is not None and not GIT_REVISION_RE.fullmatch(revision):
            raise GitLabWorkflowError(f"GitLab returned an invalid {label} revision")
    return {
        "iid": value.get("iid"),
        "url": url,
        "state": state,
        "source_branch": value.get("source_branch"),
        "target_branch": value.get("target_branch"),
        "base_revision": base_revision,
        "start_revision": diff_refs.get("start_sha"),
        "head_revision": head_revision,
        "merge_revision": merge_revision,
        "squash_revision": squash_revision,
        "detailed_merge_status": value.get("detailed_merge_status"),
        "verified": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    mr = commands.add_parser("inspect-mr", help="read immutable MR revisions and state")
    mr.add_argument("--repo", type=Path, default=Path.cwd())
    mr.add_argument("--iid", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo = _validate_repo(args.repo)
        if args.command == "inspect-mr":
            emit(inspect_merge_request(repo, args.iid))
        return 0
    except (GitLabWorkflowError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
