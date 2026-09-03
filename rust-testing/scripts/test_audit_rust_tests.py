#!/usr/bin/env python3
"""Regression tests for the Rust test-surface auditor."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from audit_rust_tests import build_inventory


class AuditRustTestsTest(unittest.TestCase):
    def test_inventory_counts_sources_and_excludes_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "src").mkdir()
            (root / "src" / "tests").mkdir()
            (root / "tests").mkdir()
            (root / "tests" / "support").mkdir()
            (root / "target" / "generated").mkdir(parents=True)
            (root / "Cargo.toml").write_text("[package]\nname = \"fixture\"\nversion = \"0.1.0\"\n")
            (root / "src" / "lib.rs").write_text(
                "use std::sync::{Arc, Mutex};\n"
                "#[cfg(test)] mod tests {\n"
                "#[test] fn plain() {}\n"
                "#[ignore = \"slow fixture\"]\n"
                "#[tokio::test] async fn timer() {\n"
                "tokio::time::sleep(std::time::Duration::from_millis(1)).await;\n"
                "}\n}\n"
            )
            (root / "tests" / "contract.rs").write_text(
                "proptest::proptest! { #[test] fn generated(value in 0u8..10) { "
                "assert!(value < 10); } }\n"
            )
            (root / "src" / "tests" / "helper.rs").write_text(
                "#[test] fn module_test_is_not_a_cargo_integration_target() {}\n"
            )
            (root / "tests" / "support" / "mod.rs").write_text(
                "pub fn integration_test_helper() {}\n"
            )
            (root / "target" / "generated" / "ignored.rs").write_text(
                "#[test] fn must_not_be_counted() {}\n"
            )

            inventory = build_inventory(root)

            self.assertEqual(inventory["cargo_manifests"], ["Cargo.toml"])
            self.assertEqual(inventory["rust_source_files"], 4)
            self.assertEqual(inventory["integration_source_files"], ["tests/contract.rs"])
            counts = inventory["counts"]
            self.assertEqual(counts["standard_test_attributes"], 3)
            self.assertEqual(counts["tokio_test_attributes"], 1)
            self.assertEqual(counts["ignored_test_attributes"], 1)
            self.assertEqual(counts["proptest_uses"], 1)
            self.assertEqual(counts["wall_clock_sleeps"], 1)
            self.assertGreater(counts["concurrency_signals"], 0)
            self.assertTrue(
                any("wall-clock sleeps" in item for item in inventory["recommendations"])
            )
            self.assertTrue(any("lexical source scan" in item for item in inventory["limitations"]))

    def test_inventory_records_expected_read_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "src/lib.rs"
            source.parent.mkdir()
            source.write_text("#[test] fn unreadable() {}\n")
            with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
                inventory = build_inventory(root)

            self.assertEqual(inventory["unreadable_rust_sources"], ["src/lib.rs"])


if __name__ == "__main__":
    unittest.main()
