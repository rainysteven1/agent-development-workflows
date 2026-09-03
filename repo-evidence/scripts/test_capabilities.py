from pathlib import Path
import unittest
from unittest import mock

import capabilities


class CapabilitiesTest(unittest.TestCase):
    def test_graft_check_uses_explicit_repository(self) -> None:
        repo = Path("/repo/task")
        calls: list[list[str]] = []

        def fake_run(command: list[str], _cwd: Path, timeout: int = 30) -> dict:
            del timeout
            calls.append(command)
            return {
                "exitCode": 0,
                "stdout": '{"graph":{"ok":true,"nodes":7},"context":{"ok":false}}',
                "stderr": "",
            }

        with mock.patch.object(
            capabilities,
            "version",
            return_value={"installed": True, "path": "/bin/graft", "version": "test"},
        ), mock.patch.object(capabilities, "run", side_effect=fake_run):
            state = capabilities.parse_graft(repo)

        self.assertEqual(["/bin/graft", "check", str(repo), "--json"], calls[0])
        self.assertTrue(state["structuralReady"])
        self.assertEqual(7, state["nodes"])

    def test_git_path_resolves_relative_to_worktree(self) -> None:
        repo = Path("/workspace/repository")
        with mock.patch.object(
            capabilities,
            "run",
            return_value={"exitCode": 0, "stdout": "../repository.git\n", "stderr": ""},
        ):
            resolved = capabilities.git_path(repo, "--git-common-dir")

        self.assertEqual(Path("/workspace/repository.git"), resolved)

    def test_git_path_rejects_failed_resolution(self) -> None:
        with mock.patch.object(
            capabilities,
            "run",
            return_value={"exitCode": 1, "stdout": "", "stderr": "missing"},
        ), self.assertRaisesRegex(SystemExit, "cannot resolve"):
            capabilities.git_path(Path("/workspace/repository"), "--git-common-dir")

    def test_repository_state_requires_full_head(self) -> None:
        with mock.patch.object(
            capabilities,
            "run",
            return_value={"exitCode": 1, "stdout": "", "stderr": "unborn"},
        ), self.assertRaisesRegex(SystemExit, "full HEAD"):
            capabilities.repository_state(Path("/workspace/repository"))

    def test_repository_state_accepts_sha256_head(self) -> None:
        responses = [
            {"exitCode": 0, "stdout": f"{'a' * 64}\n", "stderr": ""},
            {"exitCode": 0, "stdout": "", "stderr": ""},
            {"exitCode": 0, "stdout": "../repository.git\n", "stderr": ""},
        ]
        with mock.patch.object(capabilities, "run", side_effect=responses), mock.patch.object(
            capabilities, "version", return_value={"installed": False}
        ):
            state = capabilities.repository_state(Path("/workspace/repository"))

        self.assertEqual("a" * 64, state["head"])

    def test_payload_compares_task_and_baseline_common_dirs(self) -> None:
        task = {
            "repository": "/repo/task",
            "head": "a" * 40,
            "dirty": False,
            "gitCommonDir": "/repo/repository.git",
            "tools": {},
        }
        baseline = {
            **task,
            "repository": "/repo/main",
            "head": "b" * 40,
        }
        with mock.patch.object(
            capabilities, "repository_state", side_effect=[task, baseline]
        ):
            payload = capabilities.capability_payload(
                Path("/repo/task"), Path("/repo/main")
            )

        self.assertEqual("repo-evidence-capabilities/v2", payload["format"])
        self.assertTrue(payload["sameGitCommonDir"])
        self.assertEqual("/repo/main", payload["baseline"]["repository"])


if __name__ == "__main__":
    unittest.main()
