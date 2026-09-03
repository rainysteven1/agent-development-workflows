#!/usr/bin/env python3
"""Run deterministic contract checks for the rust-testing skill."""

from __future__ import annotations

import json
import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_REFERENCES = [
    "classification-and-gates.md",
    "core-tests.md",
    "async-and-concurrency.md",
    "property-and-fuzz.md",
    "integration-and-recovery.md",
    "advanced-gates.md",
    "sources.md",
]


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    skill_path = SKILL_ROOT / "SKILL.md"
    agent_path = SKILL_ROOT / "agents" / "openai.yaml"
    eval_path = SKILL_ROOT / "evals" / "cases.json"
    audit_path = SKILL_ROOT / "scripts" / "audit_rust_tests.py"
    audit_test_path = SKILL_ROOT / "scripts" / "test_audit_rust_tests.py"

    required_paths = [skill_path, agent_path, eval_path, audit_path, audit_test_path]
    required_paths.extend(SKILL_ROOT / "references" / name for name in REQUIRED_REFERENCES)
    for path in required_paths:
        require(path.is_file(), f"missing required file: {path.relative_to(SKILL_ROOT)}", errors)

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1

    skill = skill_path.read_text(encoding="utf-8")
    agent = agent_path.read_text(encoding="utf-8")
    combined = "\n".join(
        [skill]
        + [
            (SKILL_ROOT / "references" / name).read_text(encoding="utf-8")
            for name in REQUIRED_REFERENCES
        ]
    )

    require("name: rust-testing" in skill, "frontmatter name must be rust-testing", errors)
    require("TODO" not in combined, "skill content contains a TODO placeholder", errors)
    require(len(skill.splitlines()) <= 500, "SKILL.md must stay at or below 500 lines", errors)
    for reference in REQUIRED_REFERENCES:
        require(
            f"references/{reference}" in skill,
            f"SKILL.md does not route to references/{reference}",
            errors,
        )
    require("$rust-testing" in agent, "default prompt must mention $rust-testing", errors)

    required_terms = [
        "unit",
        "component",
        "contract",
        "integration",
        "E2E",
        "recovery",
        "small",
        "medium",
        "large",
        "host",
        "container",
        "CI-isolated",
        "staging",
        "production-safe-probe",
        "nextest",
        "Loom",
        "proptest",
        "cargo-fuzz",
        "cargo-mutants",
        "Testcontainers",
        "Miri",
        "cargo-llvm-cov",
    ]
    for term in required_terms:
        require(term in combined, f"required concept missing: {term}", errors)

    forbidden_patterns = {
        r"target 80%\+": "fixed global coverage target",
        r"Default for all `assert_eq!`": "mandatory assertion dependency",
        r"At least 3 tests": "fixed test-count quota",
        r"test file is a sibling": "mandatory sibling test layout",
    }
    for pattern, label in forbidden_patterns.items():
        require(
            re.search(pattern, combined, re.IGNORECASE) is None,
            f"forbidden upstream mandate present: {label}",
            errors,
        )

    cases = json.loads(eval_path.read_text(encoding="utf-8"))
    positive = cases.get("trigger_cases", {}).get("positive", [])
    negative = cases.get("trigger_cases", {}).get("negative", [])
    behavior = cases.get("behavior_cases", [])
    require(len(positive) >= 12, "need at least 12 positive trigger cases", errors)
    require(len(negative) >= 12, "need at least 12 negative trigger cases", errors)
    require(len(behavior) >= 6, "need at least 6 behavior cases", errors)
    for case in behavior:
        require(bool(case.get("id")), "behavior case missing id", errors)
        require(bool(case.get("prompt")), "behavior case missing prompt", errors)
        require(
            len(case.get("assertions", [])) >= 3,
            f"behavior case {case.get('id', '<unknown>')} needs at least 3 assertions",
            errors,
        )

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1

    print(
        "rust-testing skill contract valid: "
        f"{len(positive)} positive triggers, {len(negative)} negative triggers, "
        f"{len(behavior)} behavior cases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
