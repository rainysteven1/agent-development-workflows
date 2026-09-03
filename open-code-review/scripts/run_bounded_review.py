#!/usr/bin/env python3
"""Run one packet-only Codex review with an explicit delivery-time budget."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import selectors
import subprocess
import sys
import time


MAX_FILES = 12
MAX_CHANGED_LINES = 800
SMALL_CHANGED_LINES = 200
SMALL_FILE_COUNT = 6
SMALL_BUDGET_SECONDS = 180
MEDIUM_BUDGET_SECONDS = 300
REVIEW_MODEL = "gpt-5.6-luna"
REVIEW_REASONING_EFFORT = "max"
FALLBACK_REASONING_EFFORT = "xhigh"
FIRST_OUTPUT_TIMEOUT_SECONDS = 90


OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "reviewed_paths",
        "findings",
        "overall_correctness",
        "overall_explanation",
        "overall_confidence_score",
    ],
    "properties": {
        "reviewed_paths": {
            "type": "array",
            "items": {"type": "string"},
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["severity", "path", "line", "title", "body", "reproduction", "fix"],
                "properties": {
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "path": {"type": "string"},
                    "line": {"type": "integer", "minimum": 1},
                    "title": {"type": "string", "maxLength": 100},
                    "body": {"type": "string", "minLength": 1},
                    "reproduction": {"type": "string", "minLength": 1},
                    "fix": {"type": "string", "minLength": 1},
                },
            },
        },
        "overall_correctness": {
            "type": "string",
            "enum": ["patch is correct", "patch is incorrect"],
        },
        "overall_explanation": {"type": "string", "minLength": 1},
        "overall_confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


def fail(message: str) -> None:
    raise SystemExit(message)


def run(repo: Path, *args: str) -> str:
    result = subprocess.run(
        args,
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path}: {exc}")


def extract_rule_texts(rules: dict) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for group in rules.get("groups", []):
        rule = str(group.get("rule", "")).strip()
        if rule and rule not in seen:
            seen.add(rule)
            result.append(rule)
    return result


def review_budget(file_count: int, changed_lines: int) -> int:
    if file_count <= SMALL_FILE_COUNT and changed_lines <= SMALL_CHANGED_LINES:
        return SMALL_BUDGET_SECONDS
    return MEDIUM_BUDGET_SECONDS


def build_prompt(
    parent: str,
    commit: str,
    background: str,
    paths: list[str],
    rules: list[str],
    diff: str,
    verification: str,
    context: list[tuple[str, str]],
) -> str:
    context_text = "\n\n".join(f"### {path}\n```text\n{content}\n```" for path, content in context)
    rules_text = "\n\n---\n\n".join(rules) or "No additional review rules were resolved."
    return f"""You are the independent adversarial reviewer for exactly one immutable commit.

Return one structured verdict and stop. Analyze only this packet. Do not call tools, inspect the
repository, search history, or broaden into unrelated files. If the packet does not prove a
non-local claim, omit that finding instead of exploring. Report only actionable defects introduced
by this commit; deterministic formatting, lint, and test concerns already covered by verification
are not findings unless the diff demonstrates a user-visible consequence.

Parent: {parent}
Commit: {commit}
Acceptance context: {background}
Verification evidence: {verification or 'Not supplied'}
Required reviewed paths: {json.dumps(paths)}

For every finding, cite a changed path and an exact changed-line location, explain the reachable
impact, give a concrete reproduction, and propose the smallest practical fix. Set reviewed_paths to
the complete required path list. A missing path makes the review incomplete.

## Resolved rules

{rules_text}

## Bounded direct context

{context_text or 'No extra direct context was supplied.'}

## Exact parent-to-commit diff

```diff
{diff}
```
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--rules", required=True, type=Path)
    parser.add_argument("--output-prefix", required=True, type=Path)
    parser.add_argument("--verification", default="")
    parser.add_argument("--context", action="append", default=[], help="repo-relative direct-context file")
    parser.add_argument("--budget-seconds", type=int)
    parser.add_argument("--first-output-timeout-seconds", type=int, default=FIRST_OUTPUT_TIMEOUT_SECONDS)
    parser.add_argument("--no-effort-fallback", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    if not (repo / ".git").exists():
        fail(f"repository worktree is unavailable: {repo}")

    commit = run(repo, "git", "rev-parse", f"{args.commit}^{{commit}}")
    parents = run(repo, "git", "show", "-s", "--format=%P", commit).split()
    if len(parents) != 1:
        fail("bounded review requires a commit with exactly one parent")
    parent = parents[0]

    manifest = load_json(args.manifest)
    rules_document = load_json(args.rules)
    if Path(str(manifest.get("repository", ""))).resolve() != repo:
        fail("manifest repository does not match --repo")
    if manifest.get("from") != parent or manifest.get("to") != commit:
        fail("manifest revisions do not match the immutable commit")

    files = manifest.get("reviewable_files", [])
    paths = [str(item["path"]) for item in files]
    changed_lines = sum(int(item.get("insertions", 0)) + int(item.get("deletions", 0)) for item in files)
    if not paths:
        fail("manifest contains no reviewable files")
    if len(paths) > MAX_FILES or changed_lines > MAX_CHANGED_LINES:
        fail(
            f"review packet is too large ({len(paths)} files, {changed_lines} changed lines); "
            "split the atomic increment or define explicit bounded review batches"
        )

    budget = args.budget_seconds or review_budget(len(paths), changed_lines)
    if budget <= 0 or budget > MEDIUM_BUDGET_SECONDS:
        fail(f"budget must be within 1..{MEDIUM_BUDGET_SECONDS} seconds")

    context: list[tuple[str, str]] = []
    for relative in args.context:
        path = (repo / relative).resolve()
        try:
            path.relative_to(repo)
        except ValueError:
            fail(f"context path leaves repository: {relative}")
        content = path.read_text(encoding="utf-8")
        if len(content.encode("utf-8")) > 40_000:
            fail(f"context file exceeds 40 KB: {relative}")
        context.append((relative, content))
    if sum(len(content.encode("utf-8")) for _, content in context) > 100_000:
        fail("combined direct context exceeds 100 KB")

    diff = run(repo, "git", "diff", "--no-ext-diff", "--unified=12", parent, commit, "--", *paths)
    prompt = build_prompt(
        parent,
        commit,
        str(manifest.get("background", "")).strip(),
        paths,
        extract_rule_texts(rules_document),
        diff,
        args.verification.strip(),
        context,
    )

    prefix = args.output_prefix.resolve()
    packet_dir = Path(str(prefix) + ".packet")
    if packet_dir.exists():
        fail(f"packet directory already exists; use a fresh output prefix: {packet_dir}")
    packet_dir.mkdir(parents=True)
    prompt_path = packet_dir / "prompt.md"
    schema_path = packet_dir / "output-schema.json"
    result_path = Path(str(prefix) + ".result.json")
    jsonl_path = Path(str(prefix) + ".jsonl")
    stderr_path = Path(str(prefix) + ".stderr.log")
    status_path = Path(str(prefix) + ".status.json")
    prompt_path.write_text(prompt, encoding="utf-8")
    schema_path.write_text(json.dumps(OUTPUT_SCHEMA, indent=2) + "\n", encoding="utf-8")

    base_status = {
        "parent_revision": parent,
        "commit_revision": commit,
        "file_count": len(paths),
        "changed_lines": changed_lines,
        "budget_seconds": budget,
        "model": REVIEW_MODEL,
        "reasoning_effort": REVIEW_REASONING_EFFORT,
        "reviewed_paths": paths,
    }
    if args.dry_run:
        status_path.write_text(json.dumps({**base_status, "status": "packet_ready"}, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({**base_status, "status": "packet_ready", "packet": str(packet_dir)}, indent=2))
        return 0

    def run_attempt(effort: str, attempt_prefix: Path) -> dict[str, object]:
        attempt_result = Path(str(attempt_prefix) + ".result.json")
        attempt_jsonl = Path(str(attempt_prefix) + ".jsonl")
        attempt_stderr = Path(str(attempt_prefix) + ".stderr.log")
        command = [
            "codex", "exec", "-p", "crs", "-m", REVIEW_MODEL,
            "-c", f'model_reasoning_effort="{effort}"',
            "-c", 'approval_policy="never"', "--sandbox", "read-only",
            "--cd", str(packet_dir), "--skip-git-repo-check",
            "--output-schema", str(schema_path), "--output-last-message", str(attempt_result), "--json", "-",
        ]
        started = time.monotonic()
        saw_model_output = False
        selector = selectors.DefaultSelector()
        with attempt_jsonl.open("w", encoding="utf-8") as stdout, attempt_stderr.open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write(prompt)
            process.stdin.close()
            selector.register(process.stdout, selectors.EVENT_READ)
            timed_out = False
            while process.poll() is None:
                remaining = budget - (time.monotonic() - started)
                if remaining <= 0:
                    timed_out = True
                    break
                events = selector.select(min(1.0, remaining))
                for key, _ in events:
                    line = key.fileobj.readline()
                    if not line:
                        continue
                    stdout.write(line)
                    stdout.flush()
                    if '"type":"item.completed"' in line:
                        saw_model_output = True
                if not saw_model_output and time.monotonic() - started >= args.first_output_timeout_seconds:
                    timed_out = True
                    break
            if timed_out and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                stdout.write(line)
            selector.close()
        elapsed = round(time.monotonic() - started, 3)
        if timed_out:
            status = "pre_response_timeout" if not saw_model_output else "timed_out"
        elif process.returncode != 0:
            status = "failed"
        else:
            status = "completed"
        result = load_json(attempt_result) if status == "completed" and attempt_result.exists() else None
        return {"effort": effort, "status": status, "elapsed_seconds": elapsed, "result": result, "result_path": str(attempt_result), "jsonl": str(attempt_jsonl), "stderr": str(attempt_stderr), "exit_code": process.returncode}

    primary = run_attempt(REVIEW_REASONING_EFFORT, prefix.with_name(prefix.name + ".max"))
    attempts = [primary]
    if primary["status"] == "pre_response_timeout" and not args.no_effort_fallback:
        fallback = run_attempt(FALLBACK_REASONING_EFFORT, prefix.with_name(prefix.name + ".xhigh"))
        attempts.append(fallback)
        if fallback["status"] == "completed" and fallback["result"] is not None:
            result_path.write_text(json.dumps(fallback["result"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    selected = attempts[-1]
    if selected["status"] not in {"completed"} or selected["result"] is None:
        status_path.write_text(json.dumps({**base_status, "status": selected["status"], "attempts": attempts}, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({**base_status, "status": selected["status"], "attempts": attempts}, indent=2, default=str), file=sys.stderr)
        return 124 if selected["status"] in {"pre_response_timeout", "timed_out"} else int(selected.get("exit_code") or 1)

    elapsed = float(selected["elapsed_seconds"])
    result = selected["result"]
    actual_paths = result.get("reviewed_paths", [])
    status = "accepted" if actual_paths == paths and result.get("overall_correctness") == "patch is correct" else "findings"
    if actual_paths != paths:
        status = "incomplete"
    status_path.write_text(
        json.dumps({**base_status, "status": status, "elapsed_seconds": elapsed, "result": str(result_path), "selected_effort": selected["effort"], "attempts": attempts}, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({**base_status, "status": status, "elapsed_seconds": elapsed, "result": str(result_path), "selected_effort": selected["effort"], "attempts": attempts}, indent=2, default=str))
    return 0 if status in {"accepted", "findings"} else 2


if __name__ == "__main__":
    sys.exit(main())
