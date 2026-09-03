from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from memory_token import load_token


class MemoryTokenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def _credential(self, mode: int = 0o600) -> Path:
        credential = self.root / "credential.json"
        credential.write_text(json.dumps({"codex_user_key": "test-key"}), encoding="utf-8")
        credential.chmod(mode)
        return credential

    def test_loads_an_owner_only_regular_file(self) -> None:
        self.assertEqual("test-key", load_token(self._credential()))

    def test_rejects_a_symlink(self) -> None:
        credential = self._credential()
        symlink = self.root / "credential-link.json"
        symlink.symlink_to(credential)

        with self.assertRaisesRegex(ValueError, "non-symlink"):
            load_token(symlink)

    def test_rejects_a_non_owner_only_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "mode 0600"):
            load_token(self._credential(0o640))


if __name__ == "__main__":
    unittest.main()
