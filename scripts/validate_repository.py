#!/usr/bin/env python3
"""Validate the self-maintained Skill repository inventory and boundaries."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


EXPECTED_REPOSITORY = "agent-development-workflows"
EXPECTED_OWNERSHIP = "self-maintained"
EXTERNAL_SKILLS = {
    "anysearch",
    "brandkit",
    "find-skills",
    "lark-doc",
    "merge-flow",
    "paseo",
    "pipeline-monitor",
    "setup-repo",
    "workbuddy-guide",
}
SENSITIVE_NAMES = {".env", ".env.local"}
SENSITIVE_SUFFIXES = {".key", ".p12", ".pem", ".pfx"}
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "skills.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"cannot load skills.json: {error}"]
    if not isinstance(manifest, dict):
        return ["skills.json must contain an object"]
    if manifest.get("schema_version") != 1:
        errors.append("skills.json has an unsupported schema_version")
    if manifest.get("repository") != EXPECTED_REPOSITORY:
        errors.append(f"repository must be {EXPECTED_REPOSITORY}")
    if manifest.get("ownership") != EXPECTED_OWNERSHIP:
        errors.append(f"ownership must be {EXPECTED_OWNERSHIP}")

    entries = manifest.get("skills")
    if not isinstance(entries, list):
        return [*errors, "skills must be a list"]
    names: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"skills[{index}] must be an object")
            continue
        name = entry.get("name")
        category = entry.get("category")
        if not isinstance(name, str) or not SKILL_NAME.fullmatch(name):
            errors.append(f"skills[{index}] has an invalid name")
            continue
        if not isinstance(category, str) or not SKILL_NAME.fullmatch(category):
            errors.append(f"skill {name} has an invalid category")
        names.append(name)
    if names != sorted(names):
        errors.append("manifest skill names must be sorted")
    if len(names) != len(set(names)):
        errors.append("manifest skill names must be unique")
    external = sorted(set(names) & EXTERNAL_SKILLS)
    if external:
        errors.append(f"external Skills are forbidden: {', '.join(external)}")

    skill_roots: list[Path] = []
    for child in root.iterdir():
        if not (child / "SKILL.md").is_file():
            continue
        if child.is_symlink():
            errors.append(f"repository Skill directory is a symlink: {child.name}")
            continue
        if child.is_dir():
            skill_roots.append(child)
    disk_names = sorted(child.name for child in skill_roots)
    if names != disk_names:
        errors.append(
            f"manifest/disk mismatch: manifest={names!r}, disk={disk_names!r}"
        )

    for name in disk_names:
        skill_root = root / name
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = re.match(
            r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)",
            skill_text,
            re.DOTALL,
        )
        if frontmatter is None or re.search(
            rf"(?m)^name:\s*[\"']?{re.escape(name)}[\"']?\s*$",
            frontmatter.group(1),
        ) is None:
            errors.append(f"{name}/SKILL.md frontmatter name does not match its directory")
        for artifact in skill_root.rglob("*"):
            if artifact.is_symlink():
                errors.append(f"repository Skill contains a symlink: {artifact.relative_to(root)}")
            if artifact.is_file() and (
                artifact.name in SENSITIVE_NAMES or artifact.suffix in SENSITIVE_SUFFIXES
            ):
                errors.append(f"repository Skill contains a sensitive file: {artifact.relative_to(root)}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    errors = validate_repository(root)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1
    count = len(json.loads((root / "skills.json").read_text(encoding="utf-8"))["skills"])
    print(f"Validated {count} self-maintained Skills in {EXPECTED_REPOSITORY}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
