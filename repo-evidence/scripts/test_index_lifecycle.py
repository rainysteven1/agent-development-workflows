from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("index_lifecycle.py")


class IndexLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="index-lifecycle-test-")
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "commands.log"
        self.environment = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "INDEX_TEST_LOG": str(self.log),
        }
        self._write_tool(
            "graft",
            """#!/bin/sh
set -eu
if [ "$1" = "--version" ]; then echo "${GRAFT_TEST_VERSION:-0.16.0}"; exit 0; fi
repo="$2"
printf 'graft %s %s\n' "$1" "$repo" >> "$INDEX_TEST_LOG"
case "$1" in
  build)
    mkdir -p "$repo/graft/.cache"
    git -C "$repo" rev-parse HEAD > "$repo/graft/.cache/revision"
    ;;
  check)
    test "$(cat "$repo/graft/.cache/revision")" = "$(git -C "$repo" rev-parse HEAD)"
    if [ "${GRAFT_TEST_MALFORMED:-0}" = "1" ]; then
      printf '%s\n' 'not-json'
    else
      printf '%s\n' '{"graph":{"ok":true}}'
    fi
    ;;
  *) exit 2 ;;
esac
""",
        )
        self._write_tool(
            "rsync",
            """#!/usr/bin/env python3
import os
from pathlib import Path
import shutil
import sys

if "--delete" in sys.argv:
    raise SystemExit(97)
source = Path(sys.argv[-2].removesuffix("/"))
destination = Path(sys.argv[-1].removesuffix("/"))
with Path(os.environ["INDEX_TEST_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write("rsync " + " ".join(sys.argv[1:]) + "\\n")
destination.mkdir(parents=True, exist_ok=True)
for child in source.iterdir():
    target = destination / child.name
    if child.is_dir():
        shutil.copytree(child, target, dirs_exist_ok=True)
    else:
        shutil.copy2(child, target)
""",
        )
        self._write_tool(
            "zg",
            """#!/bin/sh
set -eu
if [ "$1" = "--version" ]; then echo '0.2.1'; exit 0; fi
repo="$2"
printf 'zg %s %s\n' "$1" "$repo" >> "$INDEX_TEST_LOG"
case "$1" in
  index)
    mkdir -p "$repo/.zvec-grep"
    git -C "$repo" rev-parse HEAD > "$repo/.zvec-grep/revision"
    ;;
  status)
    test -f "$repo/.zvec-grep/revision"
    ;;
  *) exit 2 ;;
esac
""",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_tool(self, name: str, content: str) -> None:
        path = self.bin / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def _run(
        self,
        command: list[str],
        *,
        cwd: Path,
        expected: int = 0,
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(expected, completed.returncode, completed.stderr or completed.stdout)
        return completed

    def _git(self, repo: Path, *arguments: str) -> str:
        return self._run(["git", "-C", str(repo), *arguments], cwd=repo).stdout.strip()

    def _create_repository(self) -> Path:
        repo = self.root / "canonical"
        repo.mkdir()
        self._run(["git", "init", "-b", "main"], cwd=repo)
        self._git(repo, "config", "user.name", "Index Lifecycle Test")
        self._git(repo, "config", "user.email", "index@example.invalid")
        (repo / ".gitignore").write_text(
            "graft/\n.graft/\n.zvec-grep/\n", encoding="utf-8"
        )
        (repo / "source.txt").write_text("baseline\n", encoding="utf-8")
        self._git(repo, "add", ".gitignore", "source.txt")
        self._git(repo, "commit", "-m", "test: seed repository")
        return repo

    def _lifecycle(self, repo: Path, *arguments: str, expected: int = 0) -> dict:
        completed = self._run(
            [sys.executable, str(SCRIPT), *arguments, "--repo", str(repo)],
            cwd=repo,
            expected=expected,
        )
        return json.loads(completed.stdout)

    def test_hooks_converge_canonical_and_prepare_private_graft_snapshot(self) -> None:
        canonical = self._create_repository()
        configured = self._lifecycle(
            canonical,
            "configure",
            "--target-branch",
            "main",
            "--bootstrap-indexes",
            "--apply",
        )
        self.assertTrue(configured["verified"])
        self.assertTrue((canonical / "graft/.cache/revision").is_file())
        self.assertTrue((canonical / ".zvec-grep/revision").is_file())
        common_value = Path(self._git(canonical, "rev-parse", "--git-common-dir"))
        common_dir = (
            (canonical / common_value).resolve()
            if not common_value.is_absolute()
            else common_value.resolve()
        )
        for event in ("post-checkout", "post-merge", "post-rewrite"):
            hook = common_dir / "hooks" / event
            self.assertTrue(hook.is_file())
            self.assertIn("repo-evidence:index-lifecycle:v1", hook.read_text(encoding="utf-8"))

        task = self.root / "task"
        self._git(canonical, "worktree", "add", "-b", "feat/test", str(task), "main")
        self.assertTrue((task / "graft/.cache/revision").is_file())
        self.assertFalse((task / ".zvec-grep").exists())
        self.assertTrue((canonical / ".zvec-grep/revision").is_file())
        state_path = common_dir / "repo-evidence" / "index-state.json"
        hook_state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertTrue(hook_state["tasks"][str(task)]["snapshotCopied"])
        self.assertNotIn("--delete", self.log.read_text(encoding="utf-8"))
        ownership = task / "graft/.repo-evidence-managed.json"
        ownership.write_text('{"replaced": true}\n', encoding="utf-8")
        (task / "graft/unmanaged-after-state.txt").write_text("preserve\n", encoding="utf-8")
        replaced = self._lifecycle(task, "prepare-worktree", "--apply", expected=2)
        self.assertIn("not managed", replaced["error"])
        ownership.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "taskWorktree": str(task),
                    "gitCommonDir": str(common_dir),
                }
            ),
            encoding="utf-8",
        )
        hook_state["tasks"][str(task)]["status"] = "failed"
        state_path.write_text(json.dumps(hook_state), encoding="utf-8")
        retried = self._lifecycle(task, "prepare-worktree", "--apply")
        self.assertEqual("ready", retried["status"])

        (task / "source.txt").write_text("task change\n", encoding="utf-8")
        self._git(task, "add", "source.txt")
        self._git(task, "commit", "-m", "feat: change task source")
        task_result = self._lifecycle(task, "prepare-worktree", "--apply")
        self.assertEqual("ready", task_result["status"])
        self.assertFalse(task_result["snapshotCopied"])
        task_head = self._git(task, "rev-parse", "HEAD")
        self.assertEqual(
            task_head, (task / "graft/.cache/revision").read_text(encoding="utf-8").strip()
        )

        self._git(canonical, "merge", "--ff-only", "feat/test")
        main_head = self._git(canonical, "rev-parse", "HEAD")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(main_head, state["canonical"]["revision"])
        self.assertEqual(
            main_head,
            (canonical / ".zvec-grep/revision").read_text(encoding="utf-8").strip(),
        )

        before = self.log.read_text(encoding="utf-8")
        repeated = self._lifecycle(canonical, "converge", "--apply")
        self.assertEqual("already-ready", repeated["status"])
        after = self.log.read_text(encoding="utf-8")
        self.assertEqual(before.count("graft build"), after.count("graft build"))
        self.assertEqual(before.count("zg index"), after.count("zg index"))
        self.assertGreater(after.count("graft check"), before.count("graft check"))

        (canonical / "graft/.cache/revision").unlink()
        repaired = self._lifecycle(canonical, "converge", "--apply")
        self.assertEqual("ready", repaired["status"])
        repaired_log = self.log.read_text(encoding="utf-8")
        self.assertEqual(after.count("graft build") + 1, repaired_log.count("graft build"))

        state_before_drift = state_path.read_text(encoding="utf-8")
        self.environment["GRAFT_TEST_VERSION"] = "0.17.0"
        drift = self._lifecycle(canonical, "status", expected=2)
        self.assertIn("version changed", drift["error"])
        self.assertEqual(state_before_drift, state_path.read_text(encoding="utf-8"))

    def test_non_ancestor_task_uses_local_build_without_snapshot_copy(self) -> None:
        canonical = self._create_repository()
        self._lifecycle(
            canonical,
            "configure",
            "--target-branch",
            "main",
            "--bootstrap-indexes",
            "--apply",
        )
        other = self.root / "other"
        other.mkdir()
        self._run(["git", "init", "-b", "other"], cwd=other)
        self._git(other, "config", "user.name", "Index Lifecycle Test")
        self._git(other, "config", "user.email", "index@example.invalid")
        (other / "unrelated.txt").write_text("unrelated\n", encoding="utf-8")
        self._git(other, "add", "unrelated.txt")
        self._git(other, "commit", "-m", "test: unrelated history")
        self._git(
            canonical,
            "fetch",
            str(other / ".git"),
            "HEAD:refs/heads/unrelated",
        )

        before = self.log.read_text(encoding="utf-8").count("rsync ")
        task = self.root / "unrelated-task"
        self._git(canonical, "worktree", "add", str(task), "unrelated")
        after = self.log.read_text(encoding="utf-8").count("rsync ")
        self.assertEqual(before, after)
        self.assertTrue((task / "graft/.cache/revision").is_file())
        self.assertFalse((task / ".zvec-grep").exists())

    def test_malformed_graft_check_never_records_ready_state(self) -> None:
        canonical = self._create_repository()
        self.environment["GRAFT_TEST_MALFORMED"] = "1"
        result = self._lifecycle(
            canonical,
            "configure",
            "--target-branch",
            "main",
            "--bootstrap-indexes",
            "--apply",
            expected=2,
        )
        self.assertIn("graph.ok=true", result["error"])
        state_path = canonical / ".git/repo-evidence/index-state.json"
        self.assertFalse(state_path.exists())

    def test_prepare_refuses_unmanaged_existing_task_cache(self) -> None:
        canonical = self._create_repository()
        task = self.root / "preexisting-task"
        self._git(canonical, "worktree", "add", "-b", "feat/preexisting", str(task), "main")
        (task / "graft").mkdir()
        (task / "graft/unowned.txt").write_text("unowned\n", encoding="utf-8")
        self._lifecycle(
            canonical,
            "configure",
            "--target-branch",
            "main",
            "--bootstrap-indexes",
            "--apply",
        )

        result = self._lifecycle(task, "prepare-worktree", "--apply", expected=2)
        self.assertIn("not managed", result["error"])
        self.assertEqual("unowned\n", (task / "graft/unowned.txt").read_text(encoding="utf-8"))

    def test_prepare_refuses_unmanaged_cache_file(self) -> None:
        canonical = self._create_repository()
        task = self.root / "preexisting-file-task"
        self._git(canonical, "worktree", "add", "-b", "feat/cache-file", str(task), "main")
        (task / "graft").write_text("unowned file\n", encoding="utf-8")
        self._lifecycle(
            canonical,
            "configure",
            "--target-branch",
            "main",
            "--bootstrap-indexes",
            "--apply",
        )

        result = self._lifecycle(task, "prepare-worktree", "--apply", expected=2)
        self.assertIn("not managed", result["error"])
        self.assertEqual("unowned file\n", (task / "graft").read_text(encoding="utf-8"))

    def test_prepare_refuses_symlinked_task_cache(self) -> None:
        canonical = self._create_repository()
        task = self.root / "symlink-task"
        self._git(canonical, "worktree", "add", "-b", "feat/symlink", str(task), "main")
        external = self.root / "external-cache"
        external.mkdir()
        (task / "graft").symlink_to(external, target_is_directory=True)
        self._lifecycle(
            canonical,
            "configure",
            "--target-branch",
            "main",
            "--bootstrap-indexes",
            "--apply",
        )

        result = self._lifecycle(task, "prepare-worktree", "--apply", expected=2)
        self.assertIn("symlinked", result["error"])
        self.assertEqual([], list(external.iterdir()))

    def test_configuration_refuses_to_overwrite_existing_hook(self) -> None:
        canonical = self._create_repository()
        hook = canonical / ".git/hooks/post-merge"
        hook.write_text("#!/bin/sh\necho existing\n", encoding="utf-8")
        result = self._lifecycle(
            canonical,
            "configure",
            "--target-branch",
            "main",
            "--bootstrap-indexes",
            expected=2,
        )
        self.assertEqual("failed", result["status"])
        self.assertIn("refusing to overwrite", result["error"])
        self.assertEqual("#!/bin/sh\necho existing\n", hook.read_text(encoding="utf-8"))

    def test_configuration_refuses_symlinked_hook(self) -> None:
        canonical = self._create_repository()
        external = self.root / "external-hook"
        external.write_text("#!/bin/sh\necho external\n", encoding="utf-8")
        hook = canonical / ".git/hooks/post-merge"
        hook.symlink_to(external)

        result = self._lifecycle(
            canonical,
            "configure",
            "--target-branch",
            "main",
            "--bootstrap-indexes",
            expected=2,
        )
        self.assertIn("symlinked Git hook", result["error"])
        self.assertTrue(hook.is_symlink())
        self.assertEqual("#!/bin/sh\necho external\n", external.read_text(encoding="utf-8"))

    def test_configuration_uses_absolute_core_hooks_path(self) -> None:
        canonical = self._create_repository()
        hooks = self.root / "custom-hooks"
        self._git(canonical, "config", "core.hooksPath", str(hooks))
        result = self._lifecycle(
            canonical,
            "configure",
            "--target-branch",
            "main",
            "--bootstrap-indexes",
            "--apply",
        )
        self.assertTrue(result["verified"])
        self.assertTrue((hooks / "post-checkout").is_file())
        self.assertFalse((canonical / ".git/hooks/post-checkout").exists())

    def test_configuration_rejects_relative_core_hooks_path(self) -> None:
        canonical = self._create_repository()
        self._git(canonical, "config", "core.hooksPath", ".githooks")
        result = self._lifecycle(
            canonical,
            "configure",
            "--target-branch",
            "main",
            "--bootstrap-indexes",
            expected=2,
        )
        self.assertIn("relative core.hooksPath", result["error"])


if __name__ == "__main__":
    unittest.main()
