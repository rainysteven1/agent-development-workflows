from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import session_writer


class SessionWriterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        session_writer.trusted_codex_executables.cache_clear()
        self.addCleanup(session_writer.trusted_codex_executables.cache_clear)

    def test_uuid_discovery_rejects_symlink_outside_session_roots(self) -> None:
        session_uuid = "12345678-1234-1234-1234-123456789abc"
        sessions = self.root / "sessions"
        sessions.mkdir()
        outside = self.root / f"outside-{session_uuid}.jsonl"
        outside.write_text("{}\n", encoding="utf-8")
        (sessions / f"rollout-{session_uuid}.jsonl").symlink_to(outside)

        with (
            patch.dict(os.environ, {"CODEX_HOME": str(self.root)}),
            self.assertRaisesRegex(session_writer.RecoveryError, "no local rollout"),
        ):
            session_writer.resolve_rollout(session_uuid)

    def test_unrelated_path_executable_is_not_a_trust_anchor(self) -> None:
        fake = self.root / "bin/codex"
        fake.parent.mkdir()
        fake.write_text("#!/bin/sh\n", encoding="utf-8")
        fake.chmod(0o755)

        with patch.object(session_writer.shutil, "which", return_value=str(fake)):
            self.assertEqual(frozenset(), session_writer.trusted_codex_executables())

    def test_official_package_layout_resolves_native_executable(self) -> None:
        package = self.root / "lib/node_modules/@openai/codex"
        launcher = package / "bin/codex.js"
        launcher.parent.mkdir(parents=True)
        launcher.write_text("#!/usr/bin/env node\n", encoding="utf-8")
        launcher.chmod(0o755)
        (package / "package.json").write_text(
            json.dumps(
                {
                    "name": session_writer.CODEX_PACKAGE_NAME,
                    "bin": {"codex": "bin/codex.js"},
                    "repository": {"url": session_writer.CODEX_REPOSITORY_URL},
                }
            ),
            encoding="utf-8",
        )
        native_package = package / "node_modules/@openai/codex-linux-x64"
        native = native_package / "vendor/x86_64-unknown-linux-musl/bin/codex"
        native.parent.mkdir(parents=True)
        native.write_bytes(b"native")
        native.chmod(0o755)
        (native_package / "package.json").write_text(
            json.dumps(
                {
                    "name": session_writer.CODEX_PACKAGE_NAME,
                    "repository": {"url": session_writer.CODEX_REPOSITORY_URL},
                }
            ),
            encoding="utf-8",
        )

        with patch.object(session_writer.shutil, "which", return_value=str(launcher)):
            self.assertEqual(
                frozenset({native.resolve()}), session_writer.trusted_codex_executables()
            )


if __name__ == "__main__":
    unittest.main()
