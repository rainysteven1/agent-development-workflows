#!/usr/bin/env python3
"""Inventory a Rust repository's test surface without changing it."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".tools",
    ".vscode",
    "node_modules",
    "target",
    "vendor",
}


def is_excluded(path: Path, root: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts)


def find_files(root: Path, *, name: str | None = None, suffix: str | None = None) -> list[Path]:
    candidates = root.rglob(name) if name else root.rglob(f"*{suffix}")
    return sorted(path for path in candidates if path.is_file() and not is_excluded(path, root))


def relative_paths(paths: list[Path], root: Path) -> list[str]:
    return [path.relative_to(root).as_posix() for path in paths]


def is_cargo_integration_source(source: Path, manifests: list[Path]) -> bool:
    for manifest in manifests:
        try:
            relative = source.relative_to(manifest.parent)
        except ValueError:
            continue
        if len(relative.parts) == 2 and relative.parts[0] == "tests":
            return True
    return False


def count_pattern(pattern: str, texts: list[str]) -> int:
    compiled = re.compile(pattern, re.MULTILINE)
    return sum(len(compiled.findall(text)) for text in texts)


def build_inventory(root: Path) -> dict[str, object]:
    manifests = find_files(root, name="Cargo.toml")
    sources = find_files(root, suffix=".rs")
    source_texts: list[str] = []
    unreadable: list[str] = []
    for source in sources:
        try:
            source_texts.append(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            unreadable.append(source.relative_to(root).as_posix())

    integration_sources = [
        source
        for source in sources
        if is_cargo_integration_source(source, manifests)
        and "fuzz" not in source.relative_to(root).parts
    ]
    config_candidates = [
        root / ".config" / "nextest.toml",
        root / "nextest.toml",
        root / "rust-toolchain.toml",
        root / "rust-toolchain",
        root / "deny.toml",
    ]

    counts = {
        "standard_test_attributes": count_pattern(r"#\s*\[\s*test\s*\]", source_texts),
        "tokio_test_attributes": count_pattern(r"#\s*\[\s*tokio::test\b", source_texts),
        "ignored_test_attributes": count_pattern(
            r"#\s*\[\s*ignore(?:\s*(?:\([^]]*\)|=\s*[^]]+))?\s*\]", source_texts
        ),
        "should_panic_attributes": count_pattern(r"#\s*\[\s*should_panic\b", source_texts),
        "proptest_uses": count_pattern(
            r"\bproptest(?:::proptest)?!|\bproptest::(?!proptest!)", source_texts
        ),
        "loom_uses": count_pattern(r"\bloom::", source_texts),
        "testcontainers_uses": count_pattern(r"\btestcontainers(?::|\b)", source_texts),
        "fuzz_targets": count_pattern(r"\bfuzz_target!", source_texts),
        "wall_clock_sleeps": count_pattern(
            r"\b(?:std::thread::sleep|thread::sleep|tokio::time::sleep)\s*\(", source_texts
        ),
        "unsafe_syntax": count_pattern(
            r"\bunsafe\s+(?:fn|impl|trait|extern\b|\{)", source_texts
        ),
        "concurrency_signals": count_pattern(
            r"\b(?:Atomic[A-Za-z0-9_]*|Arc|Mutex|RwLock|Semaphore|JoinSet|spawn)\b",
            source_texts,
        ),
    }

    recommendations: list[str] = []
    if counts["wall_clock_sleeps"]:
        recommendations.append(
            "Review wall-clock sleeps; prefer events, barriers, injected clocks, or paused time."
        )
    if counts["concurrency_signals"] and not counts["loom_uses"]:
        recommendations.append(
            "Concurrency primitives are present; evaluate whether a reduced Loom model can invalidate an interleaving assumption."
        )
    if counts["unsafe_syntax"]:
        recommendations.append(
            "Unsafe syntax is present; identify owned reachable risk and evaluate targeted Miri or sanitizer coverage."
        )
    if counts["ignored_test_attributes"]:
        recommendations.append(
            "Ignored tests are present; verify each has an explicit gate, owner, and reason."
        )
    recommendations.append(
        "Classify changed tests by behavior boundary, resource size, execution location, and technique tags."
    )

    return {
        "schema_version": 1,
        "root": str(root),
        "cargo_manifests": relative_paths(manifests, root),
        "rust_source_files": len(sources),
        "integration_source_files": relative_paths(integration_sources, root),
        "tool_configs": relative_paths(
            sorted(path for path in config_candidates if path.is_file()), root
        ),
        "counts": counts,
        "unreadable_rust_sources": unreadable,
        "limitations": [
            "Counts come from a lexical source scan; comments, strings, and macro expansion can affect them.",
            "The inventory does not execute Cargo metadata, tests, CI, containers, or external systems.",
        ],
        "recommendations": recommendations,
    }


def render_text(inventory: dict[str, object]) -> str:
    lines = [f"Rust test inventory: {inventory['root']}"]
    lines.append(f"Cargo manifests: {len(inventory['cargo_manifests'])}")
    lines.append(f"Rust source files: {inventory['rust_source_files']}")
    lines.append(f"Integration source files: {len(inventory['integration_source_files'])}")
    lines.append("Counts:")
    counts = inventory["counts"]
    assert isinstance(counts, dict)
    for key, value in sorted(counts.items()):
        lines.append(f"  {key}: {value}")
    lines.append("Limitations:")
    limitations = inventory["limitations"]
    assert isinstance(limitations, list)
    for limitation in limitations:
        lines.append(f"  - {limitation}")
    lines.append("Recommendations:")
    recommendations = inventory["recommendations"]
    assert isinstance(recommendations, list)
    for recommendation in recommendations:
        lines.append(f"  - {recommendation}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Rust repository or workspace root")
    parser.add_argument("--json", action="store_true", help="emit stable JSON")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"root is not a directory: {root}")

    inventory = build_inventory(root)
    if args.json:
        print(json.dumps(inventory, indent=2, sort_keys=True))
    else:
        print(render_text(inventory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
