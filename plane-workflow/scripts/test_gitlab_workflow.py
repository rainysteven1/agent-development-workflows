#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("gitlab_workflow.py")
SPEC = importlib.util.spec_from_file_location("gitlab_workflow", SCRIPT)
assert SPEC and SPEC.loader
gitlab_workflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gitlab_workflow)


class GitLabWorkflowTests(unittest.TestCase):
    def test_merge_request_inspection_returns_revision_contract(self) -> None:
        response = {
            "iid": 12,
            "web_url": "https://git.example/group/repo/-/merge_requests/12",
            "state": "merged",
            "source_branch": "wp-12d",
            "target_branch": "main",
            "sha": "c" * 40,
            "merge_commit_sha": "d" * 40,
            "squash_commit_sha": None,
            "detailed_merge_status": "merged",
            "diff_refs": {
                "base_sha": "a" * 40,
                "start_sha": "b" * 40,
                "head_sha": "c" * 40,
            },
        }
        with mock.patch.object(gitlab_workflow, "_run_glab", return_value=response):
            result = gitlab_workflow.inspect_merge_request(Path("/repo"), 12)
        self.assertEqual("a" * 40, result["base_revision"])
        self.assertEqual("c" * 40, result["head_revision"])
        self.assertEqual("d" * 40, result["merge_revision"])
        self.assertIsNone(result["squash_revision"])

    def test_merge_request_inspection_rejects_identity_or_revision_drift(self) -> None:
        response = {
            "iid": 13,
            "web_url": "https://git.example/group/repo/-/merge_requests/13",
            "state": "opened",
            "diff_refs": {"base_sha": "short", "head_sha": "c" * 40},
        }
        with mock.patch.object(
            gitlab_workflow, "_run_glab", return_value=response
        ), self.assertRaises(gitlab_workflow.GitLabWorkflowError):
            gitlab_workflow.inspect_merge_request(Path("/repo"), 12)


if __name__ == "__main__":
    unittest.main()
