from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from validate_repository import validate_repository


class ValidateRepositoryTest(unittest.TestCase):
    def test_current_repository_is_complete(self) -> None:
        root = Path(__file__).resolve().parent.parent
        self.assertEqual([], validate_repository(root))

    def test_rejects_external_and_unlisted_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for name in ("owned-skill", "anysearch"):
                skill = root / name
                skill.mkdir()
                (skill / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: test\n---\n",
                    encoding="utf-8",
                )
            (root / "skills.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "repository": "agent-development-workflows",
                        "ownership": "self-maintained",
                        "skills": [{"name": "anysearch", "category": "external"}],
                    }
                ),
                encoding="utf-8",
            )

            errors = validate_repository(root)
            self.assertTrue(any("external Skills are forbidden" in error for error in errors))
            self.assertTrue(any("manifest/disk mismatch" in error for error in errors))

    def test_rejects_a_symlinked_skill_directory(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            tempfile.TemporaryDirectory() as external_directory,
        ):
            root = Path(temporary_directory)
            external = Path(external_directory)
            (external / "SKILL.md").write_text(
                "---\nname: owned-skill\ndescription: test\n---\n",
                encoding="utf-8",
            )
            (root / "owned-skill").symlink_to(external, target_is_directory=True)
            self._write_manifest(root, "owned-skill")

            errors = validate_repository(root)
            self.assertTrue(any("directory is a symlink" in error for error in errors))

    def test_frontmatter_name_cannot_be_spoofed_in_the_body(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            skill = root / "owned-skill"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: wrong-name\ndescription: test\n---\n\nname: owned-skill\n",
                encoding="utf-8",
            )
            self._write_manifest(root, "owned-skill")

            errors = validate_repository(root)
            self.assertTrue(any("frontmatter name" in error for error in errors))

    @staticmethod
    def _write_manifest(root: Path, name: str) -> None:
        (root / "skills.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "repository": "agent-development-workflows",
                    "ownership": "self-maintained",
                    "skills": [{"name": name, "category": "testing"}],
                }
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
