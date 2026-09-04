#!/usr/bin/env python3
"""Focused tests for the Plane workflow CLI's offline contracts."""

from __future__ import annotations

import importlib.util
import base64
import copy
import contextlib
import hashlib
import io
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import types
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("plane_workflow.py")
SPEC = importlib.util.spec_from_file_location("plane_workflow", SCRIPT)
assert SPEC and SPEC.loader
plane_workflow = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = plane_workflow
SPEC.loader.exec_module(plane_workflow)

PAGE_SCRIPT = Path(__file__).with_name("ensure_self_hosted_page.py")
PAGE_SPEC = importlib.util.spec_from_file_location("ensure_self_hosted_page", PAGE_SCRIPT)
assert PAGE_SPEC and PAGE_SPEC.loader
ensure_self_hosted_page = importlib.util.module_from_spec(PAGE_SPEC)
sys.modules[PAGE_SPEC.name] = ensure_self_hosted_page
PAGE_SPEC.loader.exec_module(ensure_self_hosted_page)


class PlaneWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = plane_workflow.load_json(
            SCRIPT.parent.parent / "assets/work-package.template.json"
        )
        self.plan.pop("template")
        self.plan["module"]["id"] = "REQ-001"
        self.plan["requirement"]["id"] = "REQ-001"
        self.plan["work_package"]["id"] = "WP-01A"
        self.plan["work_package"]["repositories"] = ["group/backend", "group/frontend"]
        self.plan["work_package"]["start_date"] = "2026-08-18"
        self.plan["work_package"]["target_date"] = "2026-08-24"
        self.plan["requirement"]["start_date"] = "2026-08-18"
        self.plan["requirement"]["target_date"] = "2026-08-24"
        for phase, start, target in zip(
            self.plan["phases"],
            ("2026-08-18", "2026-08-19", "2026-08-22"),
            ("2026-08-18", "2026-08-21", "2026-08-24"),
        ):
            phase["start_date"] = start
            phase["target_date"] = target

    def test_template_is_valid_and_renders_stable_ids(self) -> None:
        self.assertEqual([], plane_workflow.validate_plan(self.plan))
        rendered = plane_workflow.render_objects(self.plan, "delivery-v1")
        self.assertEqual("module:REQ-001", rendered["module"]["external_id"])
        self.assertEqual("requirement:REQ-001", rendered["requirement"]["external_id"])
        self.assertEqual("work-package:WP-01A", rendered["work_package"]["external_id"])
        self.assertEqual(
            ["phase:WP-01A:0", "phase:WP-01A:1", "phase:WP-01A:2"],
            [phase["external_id"] for phase in rendered["phases"]],
        )
        self.assertEqual(
            {"group/backend", "group/frontend"},
            plane_workflow.work_package_repositories(
                rendered["work_package"]["description_html"]
            ),
        )
        self.assertIn('data-type="taskList"', rendered["phases"][0]["description_html"])

    def test_requirement_dates_can_cover_multiple_sibling_work_packages(self) -> None:
        self.plan["requirement"]["start_date"] = "2026-08-01"
        self.plan["requirement"]["target_date"] = "2026-08-31"
        rendered = plane_workflow.render_objects(self.plan, "delivery-v1")
        self.assertEqual("2026-08-01", rendered["requirement"]["start_date"])
        self.assertEqual("2026-08-31", rendered["requirement"]["target_date"])
        self.assertEqual("2026-08-18", rendered["work_package"]["start_date"])
        self.assertEqual("2026-08-24", rendered["work_package"]["target_date"])

    def test_work_package_dates_must_stay_inside_requirement_dates(self) -> None:
        self.plan["requirement"]["start_date"] = "2026-08-19"
        self.plan["requirement"]["target_date"] = "2026-08-23"
        errors = plane_workflow.validate_plan(self.plan)
        self.assertIn("work_package.start_date precedes Requirement start_date", errors)
        self.assertIn("work_package.target_date follows Requirement target_date", errors)

    def test_legacy_repository_migration_only_appends_missing_section(self) -> None:
        original = (
            "<h3>目标</h3><p>Keep this evidence.</p>"
            "<h3>实际证据</h3><p><code>phase-proof</code> passed.</p>"
        )
        migrated, changed = plane_workflow.append_legacy_work_package_repositories(
            original, ["platform/delivery-platform"]
        )
        self.assertTrue(changed)
        self.assertTrue(migrated.startswith(original))
        self.assertEqual(
            {"platform/delivery-platform"},
            plane_workflow.work_package_repositories(migrated),
        )
        unchanged, changed = plane_workflow.append_legacy_work_package_repositories(
            migrated, ["platform/delivery-platform"]
        )
        self.assertFalse(changed)
        self.assertEqual(migrated, unchanged)

    def test_legacy_repository_migration_refuses_rewriting_existing_set(self) -> None:
        rendered = plane_workflow.render_objects(self.plan, "delivery-v1")
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "refuses to rewrite"):
            plane_workflow.append_legacy_work_package_repositories(
                rendered["work_package"]["description_html"],
                ["platform/delivery-platform"],
            )

    def test_unedited_template_cannot_be_applied(self) -> None:
        untouched = plane_workflow.load_json(
            SCRIPT.parent.parent / "assets/work-package.template.json"
        )
        self.assertTrue(any("not executable" in error for error in plane_workflow.validate_plan(untouched)))
        untouched.pop("template")
        self.assertTrue(any("placeholder remains" in error for error in plane_workflow.validate_plan(untouched)))

    def test_plane_connection_loads_single_secure_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection = root / "plane.env"
            connection.write_text(
                "PLANE_BASE_URL=https://plane.example\nPLANE_API_KEY=secret\n",
                encoding="utf-8",
            )
            connection.chmod(0o600)
            with mock.patch.dict(
                os.environ,
                {"PLANE_CONNECTION_FILE": str(connection)},
                clear=True,
            ):
                self.assertEqual(
                    ("https://plane.example", "secret"),
                    plane_workflow._load_plane_connection(),
                )

    def test_plane_connection_rejects_insecure_file_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection = root / "plane.env"
            connection.write_text(
                "PLANE_BASE_URL=https://plane.example\nPLANE_API_KEY=secret\n",
                encoding="utf-8",
            )
            connection.chmod(0o644)
            with mock.patch.dict(
                os.environ,
                {"PLANE_CONNECTION_FILE": str(connection)},
                clear=True,
            ), self.assertRaisesRegex(plane_workflow.WorkflowError, "mode 600"):
                plane_workflow._load_plane_connection()

    def test_plane_connection_uses_default_file_and_process_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = Path(directory) / "plane.env"
            connection.write_text(
                "PLANE_BASE_URL=https://plane.example\nPLANE_API_KEY=file-secret\n",
                encoding="utf-8",
            )
            connection.chmod(0o600)
            with mock.patch.object(plane_workflow, "PLANE_CONNECTION_FILE", connection), mock.patch.dict(
                os.environ, {}, clear=True
            ):
                self.assertEqual(
                    ("https://plane.example", "file-secret"),
                    plane_workflow._load_plane_connection(),
                )
            with mock.patch.dict(
                os.environ,
                {
                    "PLANE_BASE_URL": "https://override.example",
                    "PLANE_API_KEY": "override-secret",
                    "PLANE_CONNECTION_FILE": str(Path(directory) / "missing.env"),
                },
                clear=True,
            ):
                self.assertEqual(
                    ("https://override.example", "override-secret"),
                    plane_workflow._load_plane_connection(),
                )

    def test_plane_connection_rejects_blank_process_values(self) -> None:
        invalid_values = (
            ("PLANE_BASE_URL", " "),
            ("PLANE_API_KEY", "\t"),
            ("PLANE_API_KEY", "sentinel-secret\nInjected: yes"),
        )
        for name, value in invalid_values:
            with self.subTest(name=name), mock.patch.dict(
                os.environ,
                {name: value},
                clear=True,
            ), self.assertRaisesRegex(plane_workflow.WorkflowError, name):
                plane_workflow._load_plane_connection()

    def test_plane_connection_rejects_non_regular_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.dict(
                os.environ,
                {"PLANE_CONNECTION_FILE": str(root)},
                clear=True,
            ), self.assertRaisesRegex(plane_workflow.WorkflowError, "regular file"):
                plane_workflow._load_plane_connection()

            target = root / "target.env"
            target.write_text(
                "PLANE_BASE_URL=https://plane.example\nPLANE_API_KEY=secret\n",
                encoding="utf-8",
            )
            target.chmod(0o600)
            connection = root / "plane.env"
            connection.symlink_to(target)
            with mock.patch.dict(
                os.environ,
                {"PLANE_CONNECTION_FILE": str(connection)},
                clear=True,
            ), self.assertRaisesRegex(plane_workflow.WorkflowError, "regular file"):
                plane_workflow._load_plane_connection()

    def test_plane_connection_rejects_wrong_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = Path(directory) / "plane.env"
            connection.write_text(
                "PLANE_BASE_URL=https://plane.example\nPLANE_API_KEY=secret\n",
                encoding="utf-8",
            )
            connection.chmod(0o600)
            metadata = connection.stat()
            wrong_owner = types.SimpleNamespace(
                st_mode=metadata.st_mode,
                st_uid=os.getuid() + 1,
            )
            with mock.patch.dict(
                os.environ,
                {"PLANE_CONNECTION_FILE": str(connection)},
                clear=True,
            ), mock.patch.object(
                plane_workflow.os, "fstat", return_value=wrong_owner
            ), self.assertRaisesRegex(plane_workflow.WorkflowError, "current user"):
                plane_workflow._load_plane_connection()

    def test_plane_connection_rejects_invalid_entries_without_leaking_values(self) -> None:
        invalid_files = {
            "unknown": (
                "PLANE_BASE_URL=https://plane.example\n"
                "PLANE_API_KEY=sentinel-secret\nUNKNOWN=value\n"
            ),
            "duplicate": (
                "PLANE_BASE_URL=https://plane.example\n"
                "PLANE_API_KEY=sentinel-secret\nPLANE_API_KEY=again\n"
            ),
            "missing": "PLANE_BASE_URL=https://plane.example\n",
            "whitespace": (
                "PLANE_BASE_URL= https://plane.example\nPLANE_API_KEY=sentinel-secret\n"
            ),
            "line-prefix": (
                " PLANE_BASE_URL=https://plane.example\nPLANE_API_KEY=sentinel-secret\n"
            ),
            "line-suffix": (
                "PLANE_BASE_URL=https://plane.example \nPLANE_API_KEY=sentinel-secret\n"
            ),
            "control": (
                "PLANE_BASE_URL=https://plane.example\n"
                "PLANE_API_KEY=sentinel-secret\x00suffix\n"
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            connection = Path(directory) / "plane.env"
            for name, contents in invalid_files.items():
                with self.subTest(name=name):
                    connection.write_text(contents, encoding="utf-8")
                    connection.chmod(0o600)
                    with mock.patch.dict(
                        os.environ,
                        {"PLANE_CONNECTION_FILE": str(connection)},
                        clear=True,
                    ), self.assertRaises(plane_workflow.WorkflowError) as raised:
                        plane_workflow._load_plane_connection()
                    self.assertNotIn("sentinel-secret", str(raised.exception))

    def test_plane_connection_rejects_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = Path(directory) / "plane.env"
            connection.write_bytes(b"PLANE_BASE_URL=https://plane.example\nPLANE_API_KEY=\xff\n")
            connection.chmod(0o600)
            with mock.patch.dict(
                os.environ,
                {"PLANE_CONNECTION_FILE": str(connection)},
                clear=True,
            ), self.assertRaisesRegex(plane_workflow.WorkflowError, "valid UTF-8"):
                plane_workflow._load_plane_connection()

    def test_invalid_phase_shape_is_rejected(self) -> None:
        self.plan["phases"][1]["number"] = 3
        self.plan["phases"][0]["tasks"] = ["only one"]
        errors = plane_workflow.validate_plan(self.plan)
        self.assertTrue(any("2-5" in error for error in errors))
        self.assertTrue(any("contiguous" in error for error in errors))

    def test_invalid_work_package_repository_set_is_rejected(self) -> None:
        self.plan["work_package"]["repositories"] = ["group/backend", "group/backend"]
        errors = plane_workflow.validate_plan(self.plan)
        self.assertTrue(any("must not contain duplicates" in error for error in errors))

    def test_phase_summary_requires_both_checkbox_markers(self) -> None:
        partial = (
            '<h3>具体任务</h3><ul data-type="taskList">'
            '<li data-type="taskItem" data-checked="true">'
            '<label><input type="checkbox"><span></span></label><div><p>A</p></div></li>'
            '<li data-type="taskItem" data-checked="true">'
            '<label><input type="checkbox" checked=""><span></span></label><div><p>B</p></div></li>'
            '</ul><h3>实际证据</h3><p>Evidence</p>'
        )
        summary = plane_workflow.phase_summary(partial)
        self.assertEqual(1, summary["checked"])
        self.assertEqual([0], summary["partial_marker_indexes"])
        self.assertFalse(summary["complete"])
        complete = partial.replace('<input type="checkbox">', '<input type="checkbox" checked="">')
        self.assertTrue(plane_workflow.phase_summary(complete)["complete"])

    def test_phase_completion_preserves_tasks_and_requires_actual_evidence(self) -> None:
        current = plane_workflow.render_phase_html(self.plan["phases"][0])
        completed = current.replace('data-checked="false"', 'data-checked="true"').replace(
            '<input type="checkbox">', '<input type="checkbox" checked="">'
        ).replace(
            "<h3>证据</h3><p>待本 Phase 完成后回填真实测试与运行证据。</p>",
            "<h3>实际证据</h3><ul><li><p><code>targeted-test</code> passed with runtime observation.</p></li></ul>",
        )
        summary = plane_workflow.validate_phase_completion(current, completed)
        self.assertTrue(summary["complete"])
        empty = completed.replace("<code>targeted-test</code> passed with runtime observation.", "")
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "non-placeholder"):
            plane_workflow.validate_phase_completion(current, empty)
        invented = completed.replace(self.plan["phases"][0]["tasks"][0], "invented task")
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "exactly preserve"):
            plane_workflow.validate_phase_completion(current, invented)
        trivial = completed.replace(
            "<code>targeted-test</code> passed with runtime observation.", "ok"
        )
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "non-placeholder"):
            plane_workflow.validate_phase_completion(current, trivial)

    def test_phase_start_requires_semantically_closed_predecessors(self) -> None:
        current = plane_workflow.render_phase_html(self.plan["phases"][0])
        completed = current.replace('data-checked="false"', 'data-checked="true"').replace(
            '<input type="checkbox">', '<input type="checkbox" checked="">'
        ).replace(
            "<h3>证据</h3><p>待本 Phase 完成后回填真实测试与运行证据。</p>",
            "<h3>实际证据</h3><p>targeted-test passed and the usage result was observed.</p>",
        )
        phases = [
            {"external_id": "phase:WP-01A:0", "state": "done", "description_html": completed},
            {"external_id": "phase:WP-01A:1", "state": "todo", "description_html": current},
        ]
        target = plane_workflow.validate_phase_start_sequence(phases, 1, "done", "started")
        self.assertEqual("phase:WP-01A:1", target["external_id"])
        phases[0]["description_html"] = current
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "semantically complete"):
            plane_workflow.validate_phase_start_sequence(phases, 1, "done", "started")

    def test_ledger_has_one_current_item_and_all_items_unstarted(self) -> None:
        ledger = plane_workflow.render_ledger(self.plan, 0)
        self.assertIn("Checklist：`0/2`", ledger)
        self.assertIn("当前项：回读现有事实源", ledger)
        self.assertEqual(2, ledger.count("- [未开始]"))
        self.assertIn("Phase 完成前不做 partial PATCH", ledger)

    def test_repository_route_file_is_preferred_and_validated(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plane-workflow-test-") as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            route = {
                "schema_version": 1,
                "workspace": "platform",
                "project_id": "bfaa2df0-e610-4927-b0d1-53215c7686e4",
                "project_identifier": "DCP",
                "project_name": "Application Delivery Control Plane",
                "external_source": "delivery-v1",
            }
            (root / ".plane-workflow.json").write_text(json.dumps(route), encoding="utf-8")
            resolved = plane_workflow.resolve_route(root)
            self.assertEqual("platform", resolved["workspace"])
            self.assertEqual(str(root), resolved["repository"])
            self.assertTrue(resolved["evidence"].endswith(".plane-workflow.json"))

    def test_delivery_style_agents_route_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plane-workflow-agents-test-") as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "AGENTS.md").write_text(
                "Use workspace `platform`, project `DCP` (`Application Delivery Control Plane`), "
                "project UUID `bfaa2df0-e610-4927-b0d1-53215c7686e4`, and external source "
                "`delivery-v1`.\n",
                encoding="utf-8",
            )
            resolved = plane_workflow.resolve_route(root)
            self.assertEqual("DCP", resolved["project_identifier"])
            self.assertEqual("delivery-v1", resolved["external_source"])

    def test_closest_nested_agents_route_wins(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plane-workflow-nested-test-") as temporary:
            root = Path(temporary)
            nested = root / "services/admin"
            nested.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            route_line = (
                "Use workspace `{workspace}`, project `{identifier}` (`{name}`), project UUID "
                "`{project_id}`, and external source `{source}`.\n"
            )
            (root / "AGENTS.md").write_text(
                route_line.format(
                    workspace="root", identifier="ROOT", name="Root", project_id="00000000-0000-4000-8000-000000000001", source="root-v1"
                ),
                encoding="utf-8",
            )
            (nested / "AGENTS.md").write_text(
                route_line.format(
                    workspace="nested", identifier="NEST", name="Nested", project_id="00000000-0000-4000-8000-000000000002", source="nested-v1"
                ),
                encoding="utf-8",
            )
            resolved = plane_workflow.resolve_route(nested)
            self.assertEqual("nested", resolved["workspace"])
            self.assertEqual("nested-v1", resolved["external_source"])

    @staticmethod
    def _response(payload: bytes = b'{"ok": true}') -> mock.MagicMock:
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = payload
        return response

    @staticmethod
    def _transient_tls_eof() -> urllib.error.URLError:
        return urllib.error.URLError(ssl.SSLEOFError(8, "unexpected EOF"))

    def test_get_retries_transient_tls_eof_and_records_recovery(self) -> None:
        client = plane_workflow.PlaneClient("https://plane.example", "secret", "workspace", "project")
        with mock.patch.object(
            plane_workflow.urllib.request,
            "urlopen",
            side_effect=[self._transient_tls_eof(), self._response()],
        ) as urlopen:
            result = client.request("GET", "projects/project")
        self.assertEqual({"ok": True}, result)
        self.assertEqual(2, urlopen.call_count)
        self.assertEqual(
            ["transient GET transport error on configured request; retry 2/3 for projects/project"],
            client.transport_events,
        )

    def test_get_reports_exhausted_transient_retry(self) -> None:
        client = plane_workflow.PlaneClient("https://plane.example", "secret", "workspace", "project")
        with mock.patch.object(
            plane_workflow.urllib.request,
            "urlopen",
            side_effect=[self._transient_tls_eof() for _ in range(3)],
        ) as urlopen:
            with self.assertRaisesRegex(plane_workflow.WorkflowError, "after 3 safe-read attempts"):
                client.request("GET", "projects/project")
        self.assertEqual(3, urlopen.call_count)

    def test_get_retries_other_classified_transient_errors(self) -> None:
        reasons = (
            TimeoutError("timed out"),
            ConnectionResetError("connection reset"),
            ConnectionAbortedError("connection aborted"),
        )
        for reason in reasons:
            with self.subTest(reason=type(reason).__name__):
                client = plane_workflow.PlaneClient(
                    "https://plane.example", "secret", "workspace", "project"
                )
                with mock.patch.object(
                    plane_workflow.urllib.request,
                    "urlopen",
                    side_effect=[urllib.error.URLError(reason), self._response()],
                ) as urlopen:
                    self.assertEqual({"ok": True}, client.request("GET", "projects/project"))
                self.assertEqual(2, urlopen.call_count)

    def test_non_proxy_407_certificate_error_does_not_fallback(self) -> None:
        client = plane_workflow.PlaneClient("https://plane.example", "secret", "workspace", "project")
        certificate_error = urllib.error.URLError(
            ssl.SSLCertVerificationError(1, "hostname plane407.example mismatch")
        )
        with mock.patch.object(
            plane_workflow.urllib.request,
            "urlopen",
            side_effect=certificate_error,
        ) as urlopen, mock.patch.object(
            plane_workflow.urllib.request,
            "build_opener",
        ) as build_opener:
            with self.assertRaisesRegex(plane_workflow.WorkflowError, "plane407"):
                client.request("PATCH", "projects/project/work-items/item", data={"state": "started"})
        self.assertEqual(1, urlopen.call_count)
        build_opener.assert_not_called()

    def test_get_does_not_retry_dns_or_http_errors(self) -> None:
        client = plane_workflow.PlaneClient("https://plane.example", "secret", "workspace", "project")
        with mock.patch.object(
            plane_workflow.urllib.request,
            "urlopen",
            side_effect=urllib.error.URLError(OSError("Name or service not known")),
        ) as urlopen:
            with self.assertRaisesRegex(plane_workflow.WorkflowError, "Name or service not known"):
                client.request("GET", "projects/project")
        self.assertEqual(1, urlopen.call_count)

    def test_request_errors_redact_api_key(self) -> None:
        api_key = "sentinel-api-key"
        client = plane_workflow.PlaneClient(
            "https://plane.example", api_key, "workspace", "project"
        )
        http_error = urllib.error.HTTPError(
            "https://plane.example",
            401,
            "Unauthorized",
            {},
            io.BytesIO(f"credential rejected: {api_key}".encode()),
        )
        with mock.patch.object(
            plane_workflow.urllib.request,
            "urlopen",
            side_effect=http_error,
        ), self.assertRaises(plane_workflow.WorkflowError) as raised:
            client.request("GET", "projects/project")
        self.assertNotIn(api_key, str(raised.exception))
        self.assertIn("<redacted>", str(raised.exception))

        transport_error = urllib.error.URLError(OSError(f"connection rejected {api_key}"))
        with mock.patch.object(
            plane_workflow.urllib.request,
            "urlopen",
            side_effect=transport_error,
        ), self.assertRaises(plane_workflow.WorkflowError) as raised:
            client.request("POST", "projects/project/work-items", data={})
        self.assertNotIn(api_key, str(raised.exception))
        self.assertIn("<redacted>", str(raised.exception))

        http_error = urllib.error.HTTPError(
            "https://plane.example", 503, "Service Unavailable", {}, io.BytesIO(b"unavailable")
        )
        with mock.patch.object(
            plane_workflow.urllib.request,
            "urlopen",
            side_effect=http_error,
        ) as urlopen:
            with self.assertRaisesRegex(plane_workflow.WorkflowError, "HTTP 503"):
                client.request("GET", "projects/project")
        self.assertEqual(1, urlopen.call_count)

    def test_mutation_does_not_retry_transient_transport_error(self) -> None:
        for method in ("PATCH", "POST", "DELETE"):
            with self.subTest(method=method):
                client = plane_workflow.PlaneClient(
                    "https://plane.example", "secret", "workspace", "project"
                )
                with mock.patch.object(
                    plane_workflow.urllib.request,
                    "urlopen",
                    side_effect=self._transient_tls_eof(),
                ) as urlopen:
                    with self.assertRaisesRegex(plane_workflow.WorkflowError, f"Plane {method}"):
                        client.request(
                            method,
                            "projects/project/work-items/item",
                            data={"state": "started"},
                        )
                self.assertEqual(1, urlopen.call_count)

    def test_tunnel_407_uses_direct_fallback(self) -> None:
        client = plane_workflow.PlaneClient("https://plane.example", "secret", "workspace", "project")
        tunnel_error = urllib.error.URLError(
            OSError("Tunnel connection failed: 407 Proxy Authentication Required")
        )
        opener = mock.MagicMock()
        opener.open.return_value = self._response()
        with mock.patch.object(
            plane_workflow.urllib.request,
            "urlopen",
            side_effect=tunnel_error,
        ), mock.patch.object(
            plane_workflow.urllib.request,
            "build_opener",
            return_value=opener,
        ):
            self.assertEqual({"ok": True}, client.request("GET", "projects/project"))
        self.assertEqual(1, opener.open.call_count)

    def test_proxy_fallback_retries_only_the_direct_get(self) -> None:
        client = plane_workflow.PlaneClient("https://plane.example", "secret", "workspace", "project")
        proxy_error = urllib.error.HTTPError(
            "https://plane.example",
            407,
            "Proxy Authentication Required",
            {},
            io.BytesIO(),
        )
        opener = mock.MagicMock()
        opener.open.side_effect = [self._transient_tls_eof(), self._response()]
        with mock.patch.object(
            plane_workflow.urllib.request,
            "urlopen",
            side_effect=proxy_error,
        ) as urlopen, mock.patch.object(
            plane_workflow.urllib.request,
            "build_opener",
            return_value=opener,
        ):
            result = client.request("GET", "projects/project")
        self.assertEqual({"ok": True}, result)
        self.assertEqual(1, urlopen.call_count)
        self.assertEqual(2, opener.open.call_count)
        self.assertEqual(
            [
                "proxy returned HTTP 407; retried this Plane host directly",
                "transient GET transport error on direct request; retry 2/3 for projects/project",
            ],
            client.transport_events,
        )

    def test_require_proxy_disables_407_direct_fallback(self) -> None:
        client = plane_workflow.PlaneClient("https://plane.example", "secret", "workspace", "project")
        proxy_error = urllib.error.HTTPError(
            "https://plane.example",
            407,
            "Proxy Authentication Required",
            {},
            io.BytesIO(),
        )
        with mock.patch.dict(plane_workflow.os.environ, {"PLANE_REQUIRE_PROXY": "1"}), mock.patch.object(
            plane_workflow.urllib.request,
            "urlopen",
            side_effect=proxy_error,
        ), mock.patch.object(
            plane_workflow.urllib.request,
            "build_opener",
        ) as build_opener:
            with self.assertRaisesRegex(plane_workflow.WorkflowError, "HTTP 407"):
                client.request("GET", "projects/project")
        build_opener.assert_not_called()

    @staticmethod
    def _page_arguments() -> list[str]:
        return [
            "--context", "ctx", "--namespace", "plane", "--target", "deploy/api",
            "--workspace", "platform", "--project-id", "00000000-0000-4000-8000-000000000001",
        ]

    @staticmethod
    def _page_completed(result: dict, returncode: int = 0) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            returncode=returncode,
            stdout=(
                ensure_self_hosted_page.RESULT_PREFIX
                + json.dumps(result)
                + "\n"
            ),
            stderr="",
        )

    @staticmethod
    def _page_payload(run: mock.MagicMock) -> dict:
        remote_input = run.call_args.kwargs["input"]
        encoded = re.search(
            r'base64\.b64decode\("([A-Za-z0-9+/=]+)"\)', remote_input
        ).group(1)
        return json.loads(base64.b64decode(encoded))

    def test_page_helper_lists_read_only_without_owner_or_identity(self) -> None:
        completed = self._page_completed(
            {"status": "listed", "verified": True, "count": 0, "pages": []}
        )
        with mock.patch.object(
            ensure_self_hosted_page.subprocess, "run", return_value=completed
        ) as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, ensure_self_hosted_page.main([*self._page_arguments(), "--list"]))
        payload = self._page_payload(run)
        self.assertEqual("list", payload["operation"])
        self.assertFalse(payload["apply"])
        self.assertIsNone(payload["owner_id"])

    def test_page_helper_dry_run_accepts_candidate_html_and_exact_identity(self) -> None:
        completed = self._page_completed(
            {"status": "would_update", "verified": False, "changed": True}
        )
        with tempfile.TemporaryDirectory(prefix="plane-page-test-") as temporary:
            html_file = Path(temporary) / "candidate.html"
            html_file.write_text("<h1>Candidate</h1>", encoding="utf-8")
            arguments = [
                *self._page_arguments(),
                "--name", "Page",
                "--external-source", "delivery-v1",
                "--external-id", "page:decision",
                "--html-file", str(html_file),
            ]
            with mock.patch.object(
                ensure_self_hosted_page.subprocess, "run", return_value=completed
            ) as run, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, ensure_self_hosted_page.main(arguments))
        payload = self._page_payload(run)
        self.assertEqual("reconcile", payload["operation"])
        self.assertFalse(payload["apply"])
        self.assertTrue(payload["has_description_html"])
        self.assertEqual("<h1>Candidate</h1>", payload["description_html"])

    def test_page_helper_normalizes_terminal_newlines_before_hashing(self) -> None:
        completed = self._page_completed(
            {"status": "existing", "verified": True, "changed": False}
        )
        with tempfile.TemporaryDirectory(prefix="plane-page-test-") as temporary:
            html_file = Path(temporary) / "candidate.html"
            html_file.write_text("<h1>Candidate</h1>\n\n", encoding="utf-8")
            arguments = [
                *self._page_arguments(),
                "--name", "Page",
                "--html-file", str(html_file),
            ]
            with mock.patch.object(
                ensure_self_hosted_page.subprocess, "run", return_value=completed
            ) as run, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, ensure_self_hosted_page.main(arguments))
        self.assertEqual("<h1>Candidate</h1>", self._page_payload(run)["description_html"])

    def test_page_helper_apply_requires_owner_and_html(self) -> None:
        arguments = [*self._page_arguments(), "--name", "Page"]
        with mock.patch.object(
            ensure_self_hosted_page.subprocess, "run"
        ) as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, ensure_self_hosted_page.main([*arguments, "--apply"]))
            run.assert_not_called()
        with mock.patch.object(
            ensure_self_hosted_page.subprocess, "run"
        ) as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(
                2,
                ensure_self_hosted_page.main(
                    [
                        *arguments,
                        "--owner-id", "00000000-0000-4000-8000-000000000002",
                        "--apply",
                    ]
                ),
            )
            run.assert_not_called()

    def test_page_helper_exports_html_without_printing_encoded_content(self) -> None:
        content = b"<h1>Existing</h1>"
        completed = self._page_completed(
            {
                "status": "existing",
                "verified": True,
                "page": {
                    "page_id": "00000000-0000-4000-8000-000000000003",
                    "description_html_length": len(content.decode("utf-8")),
                    "description_html_sha256": hashlib.sha256(content).hexdigest(),
                    "description_html_base64": base64.b64encode(content).decode("ascii"),
                },
            }
        )
        with tempfile.TemporaryDirectory(prefix="plane-page-export-test-") as temporary:
            export_path = Path(temporary) / "page.html"
            output = io.StringIO()
            with mock.patch.object(
                ensure_self_hosted_page.subprocess, "run", return_value=completed
            ), contextlib.redirect_stdout(output):
                self.assertEqual(
                    0,
                    ensure_self_hosted_page.main(
                        [
                            *self._page_arguments(),
                            "--page-id", "00000000-0000-4000-8000-000000000003",
                            "--export-html", str(export_path),
                        ]
                    ),
                )
            self.assertEqual(content, export_path.read_bytes())
            self.assertNotIn(base64.b64encode(content).decode("ascii"), output.getvalue())

    def test_page_helper_redacts_html_when_export_verification_fails(self) -> None:
        content = b"<h1>Existing</h1>"
        encoded = base64.b64encode(content).decode("ascii")
        completed = self._page_completed(
            {
                "status": "existing",
                "verified": True,
                "page": {
                    "description_html_length": len(content.decode("utf-8")),
                    "description_html_sha256": "0" * 64,
                    "description_html_base64": encoded,
                },
            }
        )
        with tempfile.TemporaryDirectory(prefix="plane-page-export-test-") as temporary:
            output = io.StringIO()
            error = io.StringIO()
            with mock.patch.object(
                ensure_self_hosted_page.subprocess, "run", return_value=completed
            ), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                self.assertEqual(
                    1,
                    ensure_self_hosted_page.main(
                        [
                            *self._page_arguments(),
                            "--name", "Page",
                            "--export-html", str(Path(temporary) / "page.html"),
                        ]
                    ),
                )
            self.assertNotIn(encoded, output.getvalue())
            self.assertNotIn(encoded, error.getvalue())

    def test_page_helper_redacts_remote_diagnostics(self) -> None:
        sentinel = "<p>SECRET</p> SELECT * FROM pages pod/temporary-name"
        completed = types.SimpleNamespace(
            returncode=0,
            stdout=(
                sentinel
                + "\n"
                + ensure_self_hosted_page.RESULT_PREFIX
                + json.dumps({"status": "existing", "verified": True})
                + "\n"
            ),
            stderr=sentinel,
        )
        output = io.StringIO()
        error = io.StringIO()
        with mock.patch.object(
            ensure_self_hosted_page.subprocess, "run", return_value=completed
        ), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            self.assertEqual(
                0,
                ensure_self_hosted_page.main(
                    [*self._page_arguments(), "--name", "Page"]
                ),
            )
        self.assertNotIn(sentinel, output.getvalue())
        self.assertNotIn(sentinel, error.getvalue())
        self.assertEqual(2, error.getvalue().count("content withheld"))

    def test_page_helper_remote_contract_guards_update_and_verification(self) -> None:
        remote = ensure_self_hosted_page.REMOTE_SCRIPT
        self.assertIn('"ambiguous",', remote)
        self.assertIn('"identity_conflict"', remote)
        self.assertIn('"locked"', remote)
        self.assertIn("PageDetailSerializer(", remote)
        self.assertIn("partial=True", remote)
        self.assertIn("page_transaction.delay(", remote)
        self.assertIn("hashlib.sha256", remote)
        self.assertIn("refreshed = Page.objects.get(", remote)
        self.assertIn("projects=project", remote)
        self.assertIn('"created_by_id"', remote)
        self.assertIn('"updated_by_id"', remote)

    def test_page_helper_preserves_remote_conflict_exit_code(self) -> None:
        completed = self._page_completed(
            {"status": "identity_conflict", "verified": False}, returncode=4
        )
        with mock.patch.object(
            ensure_self_hosted_page.subprocess, "run", return_value=completed
        ), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                4,
                ensure_self_hosted_page.main(
                    [*self._page_arguments(), "--name", "Page"]
                ),
            )

    def test_phase_lookup_rejects_detached_parent(self) -> None:
        route = {"external_source": "delivery-v1"}
        items = [
            {"id": "wp", "name": "WP-01A", "external_source": "delivery-v1", "external_id": "work-package:WP-01A"},
            {"id": "phase", "name": "Phase 0", "parent": "other-wp", "external_source": "delivery-v1", "external_id": "phase:WP-01A:0"},
        ]

        class FakeClient:
            def work_items(self) -> list[dict]:
                return items

            def retrieve_work_item(self, item_id: str) -> dict:
                return next(item for item in items if item["id"] == item_id)

        with self.assertRaisesRegex(plane_workflow.WorkflowError, "not a direct child"):
            plane_workflow.find_phase(FakeClient(), route, "WP-01A", 0)

    def test_closure_rejects_unrelated_module_identity(self) -> None:
        route = {"external_source": "delivery-v1"}
        requirement = {"external_source": "delivery-v1", "external_id": "requirement:REQ-1"}
        valid_module = {"external_source": "delivery-v1", "external_id": "module:REQ-1"}
        plane_workflow.validate_closure_module_identity(route, requirement, valid_module)
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "unrelated Module"):
            plane_workflow.validate_closure_module_identity(
                route, requirement, {"external_source": "delivery-v1", "external_id": "module:OTHER"}
            )

    def _wp_review_fixture(self):
        route = {
            "workspace": "platform",
            "project_id": "project-id",
            "project_identifier": "DCP",
            "project_name": "Delivery",
            "external_source": "delivery-v1",
            "repository": "/repo",
        }
        rendered = plane_workflow.render_objects(self.plan, route["external_source"])
        completed_phases = []
        for index, phase in enumerate(rendered["phases"]):
            final_html = phase["description_html"].replace(
                'data-checked="false"', 'data-checked="true"'
            ).replace(
                '<input type="checkbox">', '<input type="checkbox" checked="">'
            ).replace(
                "<h3>证据</h3><p>待本 Phase 完成后回填真实测试与运行证据。</p>",
                "<h3>实际证据</h3><p>targeted test passed and runtime usage was observed.</p>",
            )
            completed_phases.append(
                {
                    "id": f"phase-{index}",
                    "parent": "wp-id",
                    "state": "done",
                    "description_html": final_html,
                    **phase,
                }
            )
            completed_phases[-1]["description_html"] = final_html
        module = {
            "id": "module-id",
            "status": "planned",
            **rendered["module"],
        }
        requirement = {
            "id": "requirement-id",
            "parent": None,
            "state": "ready",
            **rendered["requirement"],
        }
        work_package = {
            "id": "wp-id",
            "parent": requirement["id"],
            "state": "backlog",
            **{
                key: value
                for key, value in rendered["work_package"].items()
                if key not in {"parent_external_id", "label"}
            },
        }
        objects = {
            item["id"]: item
            for item in [requirement, work_package, *completed_phases]
        }

        class FakeClient:
            project_prefix = "projects/project-id"

            def project(self) -> dict:
                return {
                    "id": "project-id",
                    "identifier": "DCP",
                    "name": "Delivery",
                    "external_source": "delivery-v1",
                    "archived_at": None,
                }

            def states(self) -> list[dict]:
                return [
                    {"id": "backlog", "name": "Backlog", "group": "backlog"},
                    {"id": "ready", "name": "Ready", "group": "unstarted"},
                    {"id": "started", "name": "In Progress", "group": "started"},
                    {"id": "review", "name": "Review", "group": "started"},
                    {"id": "done", "name": "Done", "group": "completed"},
                ]

            def modules(self) -> list[dict]:
                return [module]

            def retrieve_module(self, module_id: str) -> dict:
                if module_id != module["id"]:
                    raise AssertionError(module_id)
                return module

            def work_items(self) -> list[dict]:
                return list(objects.values())

            def retrieve_work_item(self, item_id: str) -> dict:
                return objects[item_id]

            def module_work_items(self, module_id: str) -> list[dict]:
                if module_id != module["id"]:
                    raise AssertionError(module_id)
                return [{"id": item_id} for item_id in objects]

            def request(self, method: str, suffix: str, *, params=None, data=None):
                if method != "PATCH":
                    raise AssertionError((method, suffix, data))
                item_id = suffix.rsplit("/", 1)[1]
                target = module if "/modules/" in suffix else objects[item_id]
                target.update(data)
                return target

        return route, FakeClient(), module, requirement, work_package, completed_phases

    def _commit_receipt(
        self,
        *,
        repository: str = "group/backend",
        repository_path: str = "/repo/backend",
        phase: int = 0,
        parent: str | None = None,
        commit: str | None = None,
        session: str = "/root/wp01a_backend_commit_1",
    ) -> dict:
        parent = parent or "a" * 40
        commit = commit or "b" * 40
        return {
            "schema_version": 1,
            "wp_id": "WP-01A",
            "phase": phase,
            "review_scope": "atomic-commit",
            "review_mode": "ocr-delegation",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "max",
            "repository": repository,
            "repository_path": repository_path,
            "parent_revision": parent,
            "commit_revision": commit,
            "reviewer_session": session,
            "batch_count": 2,
            "synthesis": "accepted",
            "summary": "Fresh Luna review covered the immutable atomic commit and accepted it.",
            "commands": [
                f"ocr delegate preview --from {parent} --to {commit} --background request-and-tests",
                "ocr delegate rule services/backend/main.go",
            ],
            "findings": [],
        }

    def _append_review_marker(
        self, phase: dict, repository: str, commit_revision: str
    ) -> None:
        phase["description_html"] += (
            f"<p><code>{plane_workflow.COMMIT_REVIEW_MARKER_PREFIX}{repository}:"
            f"{commit_revision}:{'e' * 64}</code></p>"
        )

    def _append_review_receipt_marker(self, phase: dict, receipt: dict) -> None:
        phase["description_html"] += (
            f"<p><code>{plane_workflow.commit_review_marker(receipt)}</code></p>"
        )

    def _append_mr_receipt_markers(self, phases: list[dict], receipt: dict) -> None:
        for merge_request in receipt["merge_requests"]:
            for mapping in merge_request["commits"]:
                review = mapping.get("commit_review_receipt")
                if isinstance(review, dict):
                    self._append_review_receipt_marker(phases[mapping["phase"]], review)

    def _history_rewrite_receipt(self) -> dict:
        feature_review = self._commit_receipt(
            parent="a" * 40,
            commit="b" * 40,
            session="/root/wp01a_backend_feature_review",
        )
        fixup_review = self._commit_receipt(
            parent="b" * 40,
            commit="c" * 40,
            session="/root/wp01a_backend_fixup_review",
        )
        return {
            "schema_version": 1,
            "wp_id": "WP-01A",
            "phase": 0,
            "operation": "feature-autosquash",
            "result": "history-only",
            "repository": "group/backend",
            "repository_path": "/repo/backend",
            "original_parent_revision": "a" * 40,
            "reviewed_head_revision": "c" * 40,
            "original_commits": [
                {
                    "commit_revision": "b" * 40,
                    "parent_revision": "a" * 40,
                    "role": "feature",
                    "review_receipt": feature_review,
                },
                {
                    "commit_revision": "c" * 40,
                    "parent_revision": "b" * 40,
                    "role": "fixup",
                    "review_receipt": fixup_review,
                },
            ],
            "final_parent_revision": "a" * 40,
            "final_commit_revision": "d" * 40,
            "reviewed_tree_revision": "e" * 40,
            "final_tree_revision": "e" * 40,
            "verification_commands": [
                f"git rev-parse {'c' * 40}^{{tree}}",
                f"git rev-parse {'d' * 40}^{{tree}}",
            ],
            "operator": "codex-builder",
            "recorded_at": "2026-09-03T12:00:00+08:00",
            "summary": "Autosquash preserved the complete reviewed feature tree byte for byte.",
        }

    def _mr_receipt(self) -> dict:
        return {
            "schema_version": 1,
            "wp_id": "WP-01A",
            "merge_requests": [
                {
                    "repository": "group/backend",
                    "repository_path": "/repo/backend",
                    "url": "https://git.example/group/backend/-/merge_requests/7",
                    "state": "opened",
                    "base_revision": "a" * 40,
                    "head_revision": "b" * 40,
                    "verification_command": "python gitlab_workflow.py inspect-mr --iid 7",
                    "commits": [
                        {
                            "commit_revision": "b" * 40,
                            "phase": 0,
                            "commit_review_receipt": self._commit_receipt(
                                parent="a" * 40,
                                commit="b" * 40,
                                session="/root/wp01a_backend_direct_review",
                            ),
                        }
                    ],
                },
                {
                    "repository": "group/frontend",
                    "repository_path": "/repo/frontend",
                    "url": "https://git.example/group/frontend/-/merge_requests/8",
                    "state": "opened",
                    "base_revision": "c" * 40,
                    "head_revision": "d" * 40,
                    "verification_command": "python gitlab_workflow.py inspect-mr --iid 8",
                    "commits": [
                        {
                            "commit_revision": "d" * 40,
                            "phase": 1,
                            "commit_review_receipt": self._commit_receipt(
                                repository="group/frontend",
                                repository_path="/repo/frontend",
                                phase=1,
                                parent="c" * 40,
                                commit="d" * 40,
                                session="/root/wp01a_frontend_direct_review",
                            ),
                        }
                    ],
                },
            ],
            "result": "opened",
            "summary": "Both GitLab Merge Requests were re-read as opened at the recorded heads.",
        }

    def _merge_receipt(self) -> dict:
        return {
            "schema_version": 1,
            "wp_id": "WP-01A",
            "merge_requests": [
                {
                    "repository": "group/backend",
                    "url": "https://git.example/group/backend/-/merge_requests/7",
                    "base_revision": "a" * 40,
                    "head_revision": "b" * 40,
                    "state": "merged",
                    "merge_method": "merge",
                    "target_repository_path": "/repo/backend-main",
                    "merge_revision": "1" * 40,
                    "squash_revision": None,
                    "verification_command": "python gitlab_workflow.py inspect-mr --iid 7",
                },
                {
                    "repository": "group/frontend",
                    "url": "https://git.example/group/frontend/-/merge_requests/8",
                    "base_revision": "c" * 40,
                    "head_revision": "d" * 40,
                    "state": "merged",
                    "merge_method": "fast_forward",
                    "target_repository_path": "/repo/frontend-main",
                    "merge_revision": "2" * 40,
                    "squash_revision": None,
                    "verification_command": "python gitlab_workflow.py inspect-mr --iid 8",
                },
            ],
            "final_verification": {
                "commands": ["make test", "scripts/run-real-usage.sh"],
                "real_usage": "A post-merge request completed and its authoritative state was re-read.",
                "summary": "Post-merge regression and cross-repository real usage both passed.",
            },
            "result": "merged",
            "summary": "Every recorded GitLab Merge Request was re-read as merged successfully.",
        }

    def test_commit_receipt_requires_exact_fresh_luna_commit_scope(self) -> None:
        receipt = self._commit_receipt()
        with mock.patch.object(
            plane_workflow,
            "git_commit_parent",
            side_effect=lambda _path, commit: {
                "b" * 40: "a" * 40,
                "d" * 40: "c" * 40,
            }[commit],
        ), mock.patch.object(
            plane_workflow,
            "current_git_revision",
            side_effect=lambda path: {
                "/repo/backend": "b" * 40,
                "/repo/frontend": "d" * 40,
            }[path],
        ), mock.patch.object(plane_workflow, "git_revision_is_ancestor", return_value=True):
            normalized = plane_workflow.validate_commit_review_receipt(
                receipt, wp_id="WP-01A", phase_number=0
            )
            self.assertEqual("b" * 40, normalized["commit_revision"])
            for key, value, message in (
                ("model", "gpt-5.6-sol", "gpt-5.6-luna"),
                ("reasoning_effort", "high", "max"),
                ("reviewer_session", "phase-reviewer", "canonical fresh"),
                ("batch_count", 0, "positive integer"),
            ):
                with self.subTest(key=key), self.assertRaisesRegex(
                    plane_workflow.WorkflowError, message
                ):
                    plane_workflow.validate_commit_review_receipt(
                        {**receipt, key: value}, wp_id="WP-01A", phase_number=0
                    )

    def test_ocr_receipt_requires_complete_coverage_and_metadata(self) -> None:
        parent = "a" * 40
        commit = "b" * 40
        path = "services/backend/main.go"
        receipt = {
            "schema_version": 1, "template": False, "wp_id": "WP-01A", "phase": 0,
            "review_scope": "atomic-commit", "review_mode": "ocr",
            "ocr_version": "v1.11.1", "provider": "crs-custom", "model": "gpt-5.6-luna", "effort": "high",
            "repository": "group/backend", "repository_path": "/repo/backend",
            "parent_revision": parent, "commit_revision": commit, "session_id": "session-1234567890",
            "terminal_state": "complete", "preview_files": [path],
            "file_statuses": [{"path": path, "status": "completed"}], "rule_fingerprint": "f" * 64,
            "batch_count": 1, "synthesis": "accepted", "summary": "OCR completed all files with no findings.",
            "commands": [f"ocr review --commit {commit} --format json --output /tmp/review.json --provider crs-custom --model gpt-5.6-luna --effort high"],
            "findings": [],
        }
        with mock.patch.object(plane_workflow, "git_commit_parent", return_value=parent), mock.patch.object(plane_workflow, "current_git_revision", return_value=commit), mock.patch.object(plane_workflow, "git_revision_is_ancestor", return_value=True):
            normalized = plane_workflow.validate_commit_review_receipt(receipt, wp_id="WP-01A", phase_number=0)
        self.assertEqual("ocr", normalized["review_mode"])
        with mock.patch.object(plane_workflow, "git_commit_parent", return_value=parent), mock.patch.object(plane_workflow, "current_git_revision", return_value=commit), mock.patch.object(plane_workflow, "git_revision_is_ancestor", return_value=True), self.assertRaisesRegex(plane_workflow.WorkflowError, "terminal_state"):
            plane_workflow.validate_commit_review_receipt({**receipt, "terminal_state": "failed"}, wp_id="WP-01A", phase_number=0)

    def test_resolved_commit_receipt_requires_fixed_descendant(self) -> None:
        receipt = self._commit_receipt()
        receipt.update(
            synthesis="resolved",
            findings=[
                {
                    "severity": "high",
                    "summary": "Authorization check was missing.",
                    "disposition": "fixed",
                    "resolved_by_revision": "c" * 40,
                }
            ],
        )
        with mock.patch.object(
            plane_workflow, "git_commit_parent", return_value="a" * 40
        ), mock.patch.object(
            plane_workflow, "current_git_revision", return_value="c" * 40
        ), mock.patch.object(plane_workflow, "git_revision_is_ancestor", return_value=True):
            normalized = plane_workflow.validate_commit_review_receipt(
                receipt, wp_id="WP-01A", phase_number=0
            )
        self.assertEqual("fixed", normalized["findings"][0]["disposition"])

    def test_phase_commit_record_is_idempotent_and_session_unique(self) -> None:
        route, client, _, _, _, phases = self._wp_review_fixture()
        receipt = self._commit_receipt()
        with mock.patch.object(
            plane_workflow,
            "git_commit_parent",
            side_effect=lambda _path, commit: {
                "b" * 40: "a" * 40,
                "d" * 40: "c" * 40,
            }[commit],
        ), mock.patch.object(
            plane_workflow,
            "current_git_revision",
            side_effect=lambda path: {
                "/repo/backend": "b" * 40,
                "/repo/frontend": "d" * 40,
            }[path],
        ), mock.patch.object(plane_workflow, "git_revision_is_ancestor", return_value=True):
            applied = plane_workflow.record_phase_commit_review(
                client, route, "WP-01A", 0, receipt, apply=True
            )
            repeated = plane_workflow.record_phase_commit_review(
                client, route, "WP-01A", 0, receipt, apply=True
            )
            self.assertTrue(applied["verified"])
            self.assertTrue(repeated["already_recorded"])
            reused = self._commit_receipt(
                repository="group/frontend",
                repository_path="/repo/frontend",
                phase=1,
                parent="c" * 40,
                commit="d" * 40,
            )
            with self.assertRaisesRegex(plane_workflow.WorkflowError, "already used"):
                plane_workflow.record_phase_commit_review(
                    client, route, "WP-01A", 1, reused, apply=False
                )
            duplicate_commit = self._commit_receipt(
                phase=1, session="/root/wp01a_backend_commit_duplicate"
            )
            with self.assertRaisesRegex(plane_workflow.WorkflowError, "another Phase"):
                plane_workflow.record_phase_commit_review(
                    client, route, "WP-01A", 1, duplicate_commit, apply=False
                )
        self.assertIn(plane_workflow.commit_review_marker(receipt), phases[0]["description_html"])

    def test_phase_completion_preserves_commit_and_session_markers(self) -> None:
        rendered = plane_workflow.render_objects(self.plan, "delivery-v1")["phases"][0]
        receipt = self._commit_receipt()
        evidence = plane_workflow.render_commit_review_evidence(receipt)
        current = rendered["description_html"] + evidence
        final = current.replace('data-checked="false"', 'data-checked="true"').replace(
            '<input type="checkbox">', '<input type="checkbox" checked="">'
        ).replace(
            "<h3>证据</h3><p>待本 Phase 完成后回填真实测试与运行证据。</p>",
            "<h3>实际证据</h3><p>targeted tests passed and real usage was observed.</p>",
        )
        without_session = final.replace(
            plane_workflow.reviewer_session_marker(receipt["reviewer_session"]), "removed"
        )
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "preserve recorded"):
            plane_workflow.validate_phase_completion(current, without_session)
        self.assertTrue(plane_workflow.validate_phase_completion(current, final)["complete"])

    def test_history_rewrite_validates_feature_fixups_and_tree_equality(self) -> None:
        receipt = self._history_rewrite_receipt()
        parents = {
            "b" * 40: "a" * 40,
            "c" * 40: "b" * 40,
            "d" * 40: "a" * 40,
        }
        subjects = {
            "b" * 40: "feat(skills): add lifecycle",
            "c" * 40: "fixup! feat(skills): add lifecycle",
            "d" * 40: "feat(skills): add lifecycle",
        }
        with mock.patch.object(
            plane_workflow, "git_commit_parent", side_effect=lambda _path, commit: parents[commit]
        ), mock.patch.object(
            plane_workflow, "git_commit_subject", side_effect=lambda _path, commit: subjects[commit]
        ), mock.patch.object(
            plane_workflow, "git_tree_revision", return_value="e" * 40
        ), mock.patch.object(
            plane_workflow, "current_git_revision", return_value="d" * 40
        ), mock.patch.object(
            plane_workflow, "git_repository_slug", return_value="group/backend"
        ):
            normalized = plane_workflow.validate_history_rewrite_receipt(
                receipt, wp_id="WP-01A", phase_number=0
            )
            self.assertEqual("d" * 40, normalized["final_commit_revision"])
            with self.assertRaisesRegex(plane_workflow.WorkflowError, "tree revisions do not match"):
                plane_workflow.validate_history_rewrite_receipt(
                    {**receipt, "final_tree_revision": "f" * 40},
                    wp_id="WP-01A",
                    phase_number=0,
                )

            invalid_subjects = {**subjects, "c" * 40: "fixup! feat(skills): other feature"}
            with mock.patch.object(
                plane_workflow,
                "git_commit_subject",
                side_effect=lambda _path, commit: invalid_subjects[commit],
            ), self.assertRaisesRegex(plane_workflow.WorkflowError, "does not target"):
                plane_workflow.validate_history_rewrite_receipt(
                    receipt, wp_id="WP-01A", phase_number=0
                )

            with self.assertRaisesRegex(plane_workflow.WorkflowError, "preserve the feature"):
                plane_workflow.validate_history_rewrite_receipt(
                    {**receipt, "final_parent_revision": "9" * 40},
                    wp_id="WP-01A",
                    phase_number=0,
                )

            with mock.patch.object(
                plane_workflow, "current_git_revision", return_value="9" * 40
            ), self.assertRaisesRegex(plane_workflow.WorkflowError, "immediately"):
                plane_workflow.validate_history_rewrite_receipt(
                    receipt, wp_id="WP-01A", phase_number=0
                )

            original_final = {
                **receipt,
                "final_commit_revision": "b" * 40,
                "final_tree_revision": "e" * 40,
            }
            parents_with_original = {**parents, "b" * 40: "a" * 40}
            with mock.patch.object(
                plane_workflow,
                "git_commit_parent",
                side_effect=lambda _path, commit: parents_with_original[commit],
            ), mock.patch.object(
                plane_workflow, "current_git_revision", return_value="b" * 40
            ), self.assertRaisesRegex(plane_workflow.WorkflowError, "distinct"):
                plane_workflow.validate_history_rewrite_receipt(
                    original_final, wp_id="WP-01A", phase_number=0
                )

            with mock.patch.object(
                plane_workflow, "git_repository_slug", return_value="group/other"
            ), self.assertRaisesRegex(plane_workflow.WorkflowError, "does not match"):
                plane_workflow.validate_history_rewrite_receipt(
                    receipt, wp_id="WP-01A", phase_number=0
                )

    def test_history_rewrite_record_is_idempotent_and_satisfies_mr_mapping(self) -> None:
        route, client, _, _, _, phases = self._wp_review_fixture()
        rewrite_receipt = self._history_rewrite_receipt()
        for item in rewrite_receipt["original_commits"]:
            self._append_review_receipt_marker(phases[0], item["review_receipt"])
        parents = {
            "b" * 40: "a" * 40,
            "c" * 40: "b" * 40,
            "d" * 40: "a" * 40,
            "f" * 40: "c" * 40,
        }
        subjects = {
            "b" * 40: "feat(skills): add lifecycle",
            "c" * 40: "fixup! feat(skills): add lifecycle",
            "d" * 40: "feat(skills): add lifecycle",
        }
        with mock.patch.object(
            plane_workflow, "git_commit_parent", side_effect=lambda _path, commit: parents[commit]
        ), mock.patch.object(
            plane_workflow, "git_commit_subject", side_effect=lambda _path, commit: subjects[commit]
        ), mock.patch.object(
            plane_workflow, "git_tree_revision", return_value="e" * 40
        ), mock.patch.object(
            plane_workflow, "current_git_revision", return_value="d" * 40
        ), mock.patch.object(
            plane_workflow, "git_repository_slug", return_value="group/backend"
        ):
            bad_digest = self._history_rewrite_receipt()
            bad_review = {
                **bad_digest["original_commits"][0]["review_receipt"],
                "summary": "A different but structurally valid review conclusion was supplied.",
            }
            bad_digest["original_commits"] = [
                {**bad_digest["original_commits"][0], "review_receipt": bad_review},
                bad_digest["original_commits"][1],
            ]
            with self.assertRaisesRegex(plane_workflow.WorkflowError, "lacks review evidence"):
                plane_workflow.record_phase_history_rewrite(
                    client, route, "WP-01A", 0, bad_digest, apply=False
                )
            applied = plane_workflow.record_phase_history_rewrite(
                client, route, "WP-01A", 0, rewrite_receipt, apply=True
            )
            repeated = plane_workflow.record_phase_history_rewrite(
                client, route, "WP-01A", 0, rewrite_receipt, apply=True
            )
        self.assertTrue(applied["verified"])
        self.assertTrue(repeated["already_recorded"])

        frontend_review = self._commit_receipt(
            repository="group/frontend",
            repository_path="/repo/frontend",
            phase=1,
            parent="c" * 40,
            commit="f" * 40,
            session="/root/wp01a_frontend_rewritten_peer",
        )
        self._append_review_receipt_marker(phases[1], frontend_review)
        mr_receipt = self._mr_receipt()
        backend = mr_receipt["merge_requests"][0]
        backend["head_revision"] = "d" * 40
        backend["commits"] = [
            {
                "commit_revision": "d" * 40,
                "phase": 0,
                "history_rewrite_receipt": rewrite_receipt,
            }
        ]
        frontend = mr_receipt["merge_requests"][1]
        frontend["head_revision"] = "f" * 40
        frontend["commits"] = [
            {
                "commit_revision": "f" * 40,
                "phase": 1,
                "commit_review_receipt": frontend_review,
            }
        ]
        with mock.patch.object(
            plane_workflow, "git_commit_parent", side_effect=lambda _path, commit: parents[commit]
        ), mock.patch.object(
            plane_workflow, "git_commit_subject", side_effect=lambda _path, commit: subjects[commit]
        ), mock.patch.object(
            plane_workflow, "git_tree_revision", return_value="e" * 40
        ), mock.patch.object(
            plane_workflow, "current_git_revision", return_value="d" * 40
        ), mock.patch.object(
            plane_workflow, "git_repository_slug", return_value="group/backend"
        ), mock.patch.object(plane_workflow, "git_revision_is_ancestor", return_value=True):
            normalized = plane_workflow.validate_mr_receipt(
                mr_receipt,
                wp_id="WP-01A",
                expected_repositories={"group/backend", "group/frontend"},
                phases=phases,
                current_revisions={"/repo/backend": "d" * 40, "/repo/frontend": "f" * 40},
                commit_chains={
                    "/repo/backend": [("a" * 40, "d" * 40)],
                    "/repo/frontend": [("c" * 40, "f" * 40)],
                },
            )
        self.assertEqual("d" * 40, normalized["merge_requests"][0]["head_revision"])

    def test_mr_mapping_preserves_two_same_repository_features(self) -> None:
        _, _, _, _, _, phases = self._wp_review_fixture()
        first = self._history_rewrite_receipt()
        second_feature_review = self._commit_receipt(
            phase=1,
            parent="d" * 40,
            commit="1" * 40,
            session="/root/wp01a_backend_second_feature",
        )
        second_fixup_review = self._commit_receipt(
            phase=1,
            parent="1" * 40,
            commit="2" * 40,
            session="/root/wp01a_backend_second_fixup",
        )
        second = {
            **self._history_rewrite_receipt(),
            "phase": 1,
            "original_parent_revision": "d" * 40,
            "reviewed_head_revision": "2" * 40,
            "original_commits": [
                {
                    "commit_revision": "1" * 40,
                    "parent_revision": "d" * 40,
                    "role": "feature",
                    "review_receipt": second_feature_review,
                },
                {
                    "commit_revision": "2" * 40,
                    "parent_revision": "1" * 40,
                    "role": "fixup",
                    "review_receipt": second_fixup_review,
                },
            ],
            "final_parent_revision": "d" * 40,
            "final_commit_revision": "3" * 40,
            "reviewed_tree_revision": "4" * 40,
            "final_tree_revision": "4" * 40,
        }
        for item in first["original_commits"]:
            self._append_review_receipt_marker(phases[0], item["review_receipt"])
        for item in second["original_commits"]:
            self._append_review_receipt_marker(phases[1], item["review_receipt"])

        parents = {
            "b" * 40: "a" * 40,
            "c" * 40: "b" * 40,
            "d" * 40: "a" * 40,
            "1" * 40: "d" * 40,
            "2" * 40: "1" * 40,
            "3" * 40: "d" * 40,
        }
        subjects = {
            "b" * 40: "feat(skills): first",
            "c" * 40: "fixup! feat(skills): first",
            "d" * 40: "feat(skills): first",
            "1" * 40: "feat(skills): second",
            "2" * 40: "fixup! feat(skills): second",
            "3" * 40: "feat(skills): second",
        }
        trees = {
            "c" * 40: "e" * 40,
            "d" * 40: "e" * 40,
            "2" * 40: "4" * 40,
            "3" * 40: "4" * 40,
        }
        with mock.patch.object(
            plane_workflow, "git_commit_parent", side_effect=lambda _path, commit: parents[commit]
        ), mock.patch.object(
            plane_workflow, "git_commit_subject", side_effect=lambda _path, commit: subjects[commit]
        ), mock.patch.object(
            plane_workflow, "git_tree_revision", side_effect=lambda _path, commit: trees[commit]
        ), mock.patch.object(
            plane_workflow, "current_git_revision", return_value="3" * 40
        ), mock.patch.object(
            plane_workflow, "git_repository_slug", return_value="group/backend"
        ), mock.patch.object(plane_workflow, "git_revision_is_ancestor", return_value=True):
            first_normalized = plane_workflow.validate_history_rewrite_receipt(
                first, wp_id="WP-01A", phase_number=0, require_current_head=False
            )
            second_normalized = plane_workflow.validate_history_rewrite_receipt(
                second, wp_id="WP-01A", phase_number=1, require_current_head=False
            )
            phases[0]["description_html"] += plane_workflow.render_history_rewrite_evidence(
                first_normalized
            )
            phases[1]["description_html"] += plane_workflow.render_history_rewrite_evidence(
                second_normalized
            )
            mr_receipt = {
                "schema_version": 1,
                "wp_id": "WP-01A",
                "merge_requests": [
                    {
                        "repository": "group/backend",
                        "repository_path": "/repo/backend",
                        "url": "https://git.example/group/backend/-/merge_requests/7",
                        "state": "opened",
                        "base_revision": "a" * 40,
                        "head_revision": "3" * 40,
                        "verification_command": "python gitlab_workflow.py inspect-mr --iid 7",
                        "commits": [
                            {
                                "commit_revision": "d" * 40,
                                "phase": 0,
                                "history_rewrite_receipt": first,
                            },
                            {
                                "commit_revision": "3" * 40,
                                "phase": 1,
                                "history_rewrite_receipt": second,
                            },
                        ],
                    }
                ],
                "result": "opened",
                "summary": "Both independent backend features remain separate and fully mapped.",
            }
            normalized = plane_workflow.validate_mr_receipt(
                mr_receipt,
                wp_id="WP-01A",
                expected_repositories={"group/backend"},
                phases=phases,
                current_revisions={"/repo/backend": "3" * 40},
                commit_chains={
                    "/repo/backend": [
                        ("a" * 40, "d" * 40),
                        ("d" * 40, "3" * 40),
                    ]
                },
            )

        self.assertEqual(2, len(normalized["merge_requests"][0]["commits"]))

    def test_mr_receipt_maps_exact_chain_to_reviewed_phases(self) -> None:
        _, _, _, _, _, phases = self._wp_review_fixture()
        receipt = self._mr_receipt()
        self._append_mr_receipt_markers(phases, receipt)
        revisions = {"/repo/backend": "b" * 40, "/repo/frontend": "d" * 40}
        chains = {
            "/repo/backend": [("a" * 40, "b" * 40)],
            "/repo/frontend": [("c" * 40, "d" * 40)],
        }
        parents = {"b" * 40: "a" * 40, "d" * 40: "c" * 40}
        with mock.patch.object(
            plane_workflow, "git_commit_parent", side_effect=lambda _path, commit: parents[commit]
        ), mock.patch.object(
            plane_workflow, "current_git_revision", side_effect=lambda path: revisions[path]
        ):
            normalized = plane_workflow.validate_mr_receipt(
                receipt,
                wp_id="WP-01A",
                expected_repositories={"group/backend", "group/frontend"},
                phases=phases,
                current_revisions=revisions,
                commit_chains=chains,
            )
        self.assertEqual(2, len(normalized["merge_requests"]))
        bool_phase = self._mr_receipt()
        bool_phase["merge_requests"][0]["commits"][0]["phase"] = True
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "does not match"):
            with mock.patch.object(
                plane_workflow, "git_commit_parent", side_effect=lambda _path, commit: parents[commit]
            ), mock.patch.object(
                plane_workflow, "current_git_revision", side_effect=lambda path: revisions[path]
            ):
                plane_workflow.validate_mr_receipt(
                    bool_phase,
                    wp_id="WP-01A",
                    expected_repositories={"group/backend", "group/frontend"},
                    phases=phases,
                    current_revisions=revisions,
                    commit_chains=chains,
                )
        phases[1]["description_html"] = phases[1]["description_html"].replace(
            plane_workflow.COMMIT_REVIEW_MARKER_PREFIX, "missing:"
        )
        with self.assertRaisesRegex(
            plane_workflow.WorkflowError, "invalid review evidence"
        ):
            with mock.patch.object(
                plane_workflow, "git_commit_parent", side_effect=lambda _path, commit: parents[commit]
            ), mock.patch.object(
                plane_workflow, "current_git_revision", side_effect=lambda path: revisions[path]
            ):
                plane_workflow.validate_mr_receipt(
                    receipt,
                    wp_id="WP-01A",
                    expected_repositories={"group/backend", "group/frontend"},
                    phases=phases,
                    current_revisions=revisions,
                    commit_chains=chains,
                )

    def test_wp_review_means_mrs_exist_and_done_requires_merged_receipt(self) -> None:
        route, client, module, requirement, work_package, phases = self._wp_review_fixture()
        receipt = self._mr_receipt()
        self._append_mr_receipt_markers(phases, receipt)
        revisions = {"/repo/backend": "b" * 40, "/repo/frontend": "d" * 40}
        chains = {
            "/repo/backend": [("a" * 40, "b" * 40)],
            "/repo/frontend": [("c" * 40, "d" * 40)],
        }
        with mock.patch.object(
            plane_workflow, "current_git_revision", side_effect=lambda path: revisions[path]
        ), mock.patch.object(
            plane_workflow, "git_commit_chain", side_effect=lambda path, _base, _head: chains[path]
        ), mock.patch.object(
            plane_workflow,
            "git_commit_parent",
            side_effect=lambda path, commit: {
                ("/repo/backend", "b" * 40): "a" * 40,
                ("/repo/frontend", "d" * 40): "c" * 40,
            }[(path, commit)],
        ):
            review = plane_workflow.start_work_package_review(
                client, route, "WP-01A", receipt, apply=True
            )
        self.assertTrue(review["verified"])
        self.assertEqual("review", work_package["state"])

        merge_receipt = self._merge_receipt()
        target_revisions = {
            "/repo/backend-main": "1" * 40,
            "/repo/frontend-main": "2" * 40,
        }
        with mock.patch.object(
            plane_workflow,
            "current_git_revision",
            side_effect=lambda path: target_revisions[path],
        ), mock.patch.object(plane_workflow, "git_revision_is_ancestor", return_value=True):
            closure = plane_workflow.close_work_package(
                client, route, "WP-01A", merge_receipt, apply=True
            )
        self.assertTrue(closure["verified"])
        self.assertEqual("done", work_package["state"])
        self.assertEqual("done", requirement["state"])
        self.assertEqual("completed", module["status"])

    def test_merge_receipt_supports_explicit_squash_revision(self) -> None:
        receipt = self._merge_receipt()
        backend = receipt["merge_requests"][0]
        backend["merge_method"] = "squash"
        backend["squash_revision"] = "9" * 40
        ancestry = {
            ("/repo/backend-main", "9" * 40, "1" * 40): True,
            ("/repo/frontend-main", "d" * 40, "2" * 40): True,
        }
        normalized = plane_workflow.validate_merge_receipt(
            receipt,
            wp_id="WP-01A",
            expected_repositories={"group/backend", "group/frontend"},
            target_revisions={
                "/repo/backend-main": "1" * 40,
                "/repo/frontend-main": "2" * 40,
            },
            ancestry_results=ancestry,
        )
        self.assertEqual("9" * 40, normalized["merge_requests"][0]["squash_revision"])

    def test_wp_review_rejects_incomplete_phase_and_close_requires_review(self) -> None:
        route, client, _, _, work_package, phases = self._wp_review_fixture()
        phases[0]["state"] = "started"
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "cannot create"):
            plane_workflow.start_work_package_review(
                client, route, "WP-01A", self._mr_receipt(), apply=False
            )
        phases[0]["state"] = "done"
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "Review state"):
            plane_workflow.close_work_package(
                client, route, "WP-01A", self._merge_receipt(), apply=False
            )

    def test_hierarchy_verification_detects_field_drift(self) -> None:
        route = {
            "workspace": "platform",
            "project_id": "00000000-0000-4000-8000-000000000001",
            "project_identifier": "DCP",
            "project_name": "Delivery",
            "external_source": "delivery-v1",
        }
        rendered = plane_workflow.render_objects(self.plan, route["external_source"])
        module = {"id": "module-id", **rendered["module"]}
        requirement = {"id": "requirement-id", "parent": None, "labels": [], **rendered["requirement"]}
        work_package = {
            "id": "wp-id",
            "parent": requirement["id"],
            "labels": ["label-id"],
            **{key: value for key, value in rendered["work_package"].items() if key not in {"parent_external_id", "label"}},
        }
        phases = [
            {
                "id": f"phase-{index}",
                "parent": work_package["id"],
                "labels": ["label-id"],
                **{key: value for key, value in spec.items() if key not in {"number", "parent_external_id", "label"}},
            }
            for index, spec in enumerate(rendered["phases"])
        ]
        objects = {item["id"]: item for item in [requirement, work_package, *phases]}

        label = {"id": "label-id", "name": "WP-01A", "color": "#0F766E"}

        class FakeClient:
            def project(self) -> dict:
                return {"id": route["project_id"], "identifier": "DCP", "name": "Delivery", "external_source": "delivery-v1"}

            def modules(self) -> list[dict]:
                return [module]

            def retrieve_module(self, module_id: str) -> dict:
                return module

            def work_items(self) -> list[dict]:
                return list(objects.values())

            def retrieve_work_item(self, item_id: str) -> dict:
                return objects[item_id]

            def labels(self) -> list[dict]:
                return [label]

            def module_work_items(self, module_id: str) -> list[dict]:
                return [{"id": item_id} for item_id in objects]

        client = FakeClient()
        self.assertTrue(plane_workflow.verify_hierarchy(client, route, self.plan)["verified"])
        phases[0]["priority"] = "low"
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "priority"):
            plane_workflow.verify_hierarchy(client, route, self.plan)
        phases[0]["priority"] = rendered["phases"][0]["priority"]
        label["color"] = "#FFFFFF"
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "label color drift"):
            plane_workflow.verify_hierarchy(client, route, self.plan)

    def test_sync_apply_is_ordered_reread_and_idempotent(self) -> None:
        route = {
            "workspace": "platform",
            "project_id": "project-id",
            "project_identifier": "DCP",
            "project_name": "Delivery",
            "external_source": "delivery-v1",
        }

        class FakeClient:
            project_prefix = "projects/project-id"

            def __init__(self) -> None:
                self.log: list[str] = []
                self.module_values: list[dict] = []
                self.label_values: list[dict] = []
                self.item_values: list[dict] = []
                self.members: set[str] = set()

            def project(self) -> dict:
                return {"id": "project-id", "identifier": "DCP", "name": "Delivery", "external_source": "delivery-v1", "archived_at": None}

            def states(self) -> list[dict]:
                return [
                    {"id": "todo", "name": "Todo", "group": "unstarted"},
                    {"id": "started", "name": "In Progress", "group": "started"},
                    {"id": "done", "name": "Done", "group": "completed"},
                ]

            def modules(self) -> list[dict]:
                return list(self.module_values)

            def labels(self) -> list[dict]:
                return list(self.label_values)

            def work_items(self) -> list[dict]:
                return list(self.item_values)

            def retrieve_module(self, module_id: str) -> dict:
                self.log.append(f"retrieve-module:{module_id}")
                return next(item for item in self.module_values if item["id"] == module_id)

            def retrieve_work_item(self, item_id: str) -> dict:
                self.log.append(f"retrieve-item:{item_id}")
                return next(item for item in self.item_values if item["id"] == item_id)

            def module_work_items(self, module_id: str) -> list[dict]:
                self.log.append(f"list-members:{module_id}")
                return [{"id": item_id} for item_id in sorted(self.members)]

            def request(self, method: str, suffix: str, *, params=None, data=None):
                self.log.append(f"{method}:{suffix}")
                if method == "POST" and suffix.endswith("/modules"):
                    value = {"id": "module-id", **data}
                    self.module_values.append(value)
                    return value
                if method == "POST" and suffix.endswith("/labels"):
                    value = {"id": "label-id", **data}
                    self.label_values.append(value)
                    return value
                if method == "GET" and "/labels/" in suffix:
                    return self.label_values[0]
                if method == "POST" and suffix.endswith("/work-items"):
                    value = {"id": f"item-{len(self.item_values)}", **data}
                    self.item_values.append(value)
                    return value
                if method == "POST" and suffix.endswith("/module-issues"):
                    self.members.update(data["issues"])
                    return None
                if method == "PATCH" and "/modules/" in suffix:
                    self.module_values[0].update(data)
                    return self.module_values[0]
                if method == "PATCH" and "/labels/" in suffix:
                    self.label_values[0].update(data)
                    return self.label_values[0]
                if method == "PATCH" and "/work-items/" in suffix:
                    item_id = suffix.rsplit("/", 1)[1]
                    value = next(item for item in self.item_values if item["id"] == item_id)
                    value.update(data)
                    return value
                raise AssertionError((method, suffix, data))

        client = FakeClient()
        result = plane_workflow.reconcile_work_package(client, route, self.plan, apply=True)
        self.assertTrue(result.actions)
        self.assertIn("retrieve-module:module-id", client.log)
        for item in client.item_values:
            self.assertIn(f"retrieve-item:{item['id']}", client.log)
        self.assertLess(client.log.index("POST:projects/project-id/modules"), client.log.index("POST:projects/project-id/labels"))
        self.assertLess(client.log.index("POST:projects/project-id/labels"), client.log.index("POST:projects/project-id/work-items"))
        second = plane_workflow.reconcile_work_package(client, route, self.plan, apply=False)
        self.assertEqual([], second.actions)

    def _design_reconcile_fixture(self):
        route = {
            "workspace": "platform",
            "project_id": "project-id",
            "project_identifier": "DCP",
            "project_name": "Delivery",
            "external_source": "delivery-v1",
        }
        rendered = plane_workflow.render_objects(self.plan, route["external_source"])
        requirement = {"id": "requirement-id", "state": "ready", **rendered["requirement"]}
        work_package = {
            "id": "wp-id", "state": "backlog", "parent": requirement["id"], "labels": ["label-id"],
            **{key: value for key, value in rendered["work_package"].items() if key not in {"parent_external_id", "label"}},
        }
        phases = [
            {
                "id": f"phase-{index}", "state": "started" if index == 0 else "backlog",
                "parent": work_package["id"], "labels": ["label-id"],
                **{key: value for key, value in spec.items() if key not in {"number", "parent_external_id", "label"}},
            }
            for index, spec in enumerate(rendered["phases"])
        ]
        review_marker = f"{plane_workflow.COMMIT_REVIEW_MARKER_PREFIX}group/backend:{'a' * 40}:{'b' * 64}"
        rewrite_marker = f"{plane_workflow.HISTORY_REWRITE_MARKER_PREFIX}group/backend:{'c' * 40}:{'d' * 64}"
        design_html = phases[0]["description_html"]
        design_html = design_html.replace(
            'data-checked="false"', 'data-checked="true"', 1
        ).replace(
            '<input type="checkbox">', '<input type="checkbox" checked="">', 1
        ).replace(
            "<h3>证据</h3><p>待本 Phase 完成后回填真实测试与运行证据。</p>",
            "<h3>证据</h3><p>Existing active Phase evidence must survive reconciliation.</p>",
        )
        evidence_html = (
            f"<h3>Commit 审查记录</h3><p><code>{review_marker}</code></p>"
            f"<h3>History-only feature autosquash</h3><p><code>{rewrite_marker}</code></p>"
        )
        phases[0]["description_html"] = (
            "<div><div>" + design_html + "</div></div>"
            "<div><div>" + evidence_html + "</div></div>"
        )
        objects = {item["id"]: item for item in [requirement, work_package, *phases]}

        class FakeClient:
            project_prefix = "projects/project-id"

            def __init__(self) -> None:
                self.log: list[tuple[str, str, dict | None]] = []
                self.objects = objects

            def project(self) -> dict:
                return {"id": "project-id", "identifier": "DCP", "name": "Delivery", "external_source": "delivery-v1", "archived_at": None}

            def states(self) -> list[dict]:
                return [
                    {"id": "backlog", "name": "Backlog", "group": "backlog"},
                    {"id": "ready", "name": "Ready", "group": "unstarted"},
                    {"id": "started", "name": "In Progress", "group": "started"},
                    {"id": "review", "name": "Review", "group": "started"},
                    {"id": "done", "name": "Done", "group": "completed"},
                    {"id": "cancelled", "name": "Cancelled", "group": "cancelled"},
                ]

            def work_items(self) -> list[dict]:
                return copy.deepcopy(list(self.objects.values()))

            def retrieve_work_item(self, item_id: str) -> dict:
                return copy.deepcopy(self.objects[item_id])

            def request(self, method: str, suffix: str, *, params=None, data=None):
                self.log.append((method, suffix, data))
                if method != "PATCH":
                    raise AssertionError((method, suffix, data))
                item_id = suffix.rsplit("/", 1)[1]
                self.objects[item_id].update(data)
                return copy.deepcopy(self.objects[item_id])

        return route, FakeClient(), work_package, phases, review_marker, rewrite_marker

    def test_design_reconcile_preserves_started_phase_evidence_and_non_design_fields(self) -> None:
        route, client, work_package, phases, review_marker, rewrite_marker = self._design_reconcile_fixture()
        plan = json.loads(json.dumps(self.plan))
        plan["work_package"]["boundaries"].append("New storage boundary.")
        plan["phases"][0]["boundaries"] = ["Started phase boundary."]
        plan["phases"][1]["tasks"][0] = "Updated future task."
        snapshots = {
            item["id"]: {key: item.get(key) for key in ("name", "state", "parent", "priority", "start_date", "target_date", "labels")}
            for item in [work_package, *phases]
        }

        result = plane_workflow.reconcile_work_package_design(client, route, plan, apply=True)

        self.assertTrue(result["verified"])
        self.assertEqual(
            {"work-package:WP-01A", "phase:WP-01A:0", "phase:WP-01A:1"},
            {action["external_id"] for action in result["actions"]},
        )
        self.assertIn("New storage boundary.", work_package["description_html"])
        self.assertIn("Started phase boundary.", phases[0]["description_html"])
        self.assertIn(review_marker, phases[0]["description_html"])
        self.assertIn(rewrite_marker, phases[0]["description_html"])
        self.assertEqual(1, plane_workflow.phase_summary(phases[0]["description_html"])["checked"])
        self.assertIn("Existing active Phase evidence", phases[0]["description_html"])
        self.assertIn("Updated future task.", phases[1]["description_html"])
        for item in [work_package, *phases]:
            self.assertEqual(snapshots[item["id"]], {key: item.get(key) for key in snapshots[item["id"]]})
        self.assertTrue(all(list((data or {}).keys()) == ["description_html"] for _, _, data in client.log))
        repeated = plane_workflow.reconcile_work_package_design(client, route, plan, apply=False)
        self.assertEqual([], repeated["actions"])
        self.assertTrue(repeated["verified"])

    def test_design_reconcile_rejects_started_phase_contract_or_terminal_phase_change(self) -> None:
        route, client, _, phases, _, _ = self._design_reconcile_fixture()
        changed = json.loads(json.dumps(self.plan))
        changed["phases"][0]["tasks"][0] = "Changed active task."
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "active Phase contract"):
            plane_workflow.reconcile_work_package_design(client, route, changed, apply=False)

        phases[0]["state"] = "done"
        unchanged = json.loads(json.dumps(self.plan))
        unchanged["phases"][0]["boundaries"] = ["Late boundary."]
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "terminal or review Phase"):
            plane_workflow.reconcile_work_package_design(client, route, unchanged, apply=False)

        phases[0]["state"] = "started"
        duplicate = copy.deepcopy(phases[1])
        duplicate["id"] = "duplicate-phase"
        client.objects[duplicate["id"]] = duplicate
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "exact existing Phase set"):
            plane_workflow.reconcile_work_package_design(client, route, self.plan, apply=False)

    def test_design_sections_ignore_plane_editor_div_wrappers(self) -> None:
        wrapped = (
            '<div data-editor-node="true"><div><h3>目标</h3><p>Goal.</p></div></div>'
            "<div><h3>Commit 审查记录</h3><div><p><code>marker</code></p></div></div>"
        )
        blocks = plane_workflow._html_section_blocks(wrapped)
        self.assertEqual(
            ["目标", "Commit 审查记录"],
            [heading for heading, _ in blocks],
        )
        self.assertTrue(all(block.count("<div") == block.count("</div>") for _, block in blocks))

    def test_design_snapshot_normalizes_expanded_plane_relations(self) -> None:
        compact = {"state": "state-id", "parent": "parent-id", "labels": ["b", "a"]}
        expanded = {
            "state": {"id": "state-id", "name": "In Progress"},
            "parent": {"id": "parent-id"},
            "labels": [{"id": "a"}, {"id": "b"}],
        }
        self.assertEqual(
            plane_workflow._item_snapshot(compact),
            plane_workflow._item_snapshot(expanded),
        )

    def _unstarted_delete_fixture(self):
        route = {
            "workspace": "platform",
            "project_id": "project-id",
            "project_identifier": "DCP",
            "project_name": "Delivery",
            "external_source": "delivery-v1",
        }
        rendered = plane_workflow.render_objects(self.plan, route["external_source"])
        module = {"id": "module-id", "status": "planned", **rendered["module"]}
        requirement = {"id": "requirement-id", "state": "backlog", **rendered["requirement"]}
        work_package = {
            "id": "wp-id",
            "state": "backlog",
            "parent": requirement["id"],
            **rendered["work_package"],
        }
        phases = [
            {
                "id": f"phase-{index}",
                "state": "backlog",
                "parent": work_package["id"],
                **phase,
            }
            for index, phase in enumerate(rendered["phases"])
        ]
        objects = {
            item["id"]: item for item in [requirement, work_package, *phases]
        }

        class FakeClient:
            project_prefix = "projects/project-id"

            def project(self) -> dict:
                return {
                    "id": "project-id",
                    "identifier": "DCP",
                    "name": "Delivery",
                    "external_source": "delivery-v1",
                    "archived_at": None,
                }

            def states(self) -> list[dict]:
                return [
                    {"id": "backlog", "name": "Backlog", "group": "backlog"},
                    {"id": "ready", "name": "Ready", "group": "unstarted"},
                    {"id": "started", "name": "In Progress", "group": "started"},
                    {"id": "done", "name": "Done", "group": "completed"},
                    {"id": "cancelled", "name": "Cancelled", "group": "cancelled"},
                ]

            def modules(self) -> list[dict]:
                return [module]

            def retrieve_module(self, module_id: str) -> dict:
                if module_id != module["id"]:
                    raise AssertionError(module_id)
                return module

            def work_items(self) -> list[dict]:
                return list(objects.values())

            def retrieve_work_item(self, item_id: str) -> dict:
                return objects[item_id]

            def module_work_items(self, module_id: str) -> list[dict]:
                if module_id != module["id"]:
                    raise AssertionError(module_id)
                return [{"id": item_id} for item_id in objects]

            def request(self, method: str, suffix: str, *, params=None, data=None):
                if method != "DELETE":
                    raise AssertionError((method, suffix, data))
                item_id = suffix.rsplit("/", 1)[1]
                objects.pop(item_id)
                return None

        return route, FakeClient(), module, requirement, work_package, phases, objects

    def test_delete_unstarted_work_package_is_child_first_and_preserves_module(self) -> None:
        route, client, module, _, _, phases, objects = self._unstarted_delete_fixture()
        dry_run = plane_workflow.delete_unstarted_work_package(
            client, route, self.plan, apply=False
        )
        self.assertEqual(len(phases) + 2, len(dry_run["actions"]))
        self.assertEqual("phase", dry_run["actions"][0]["kind"])
        self.assertEqual("requirement", dry_run["actions"][-1]["kind"])
        self.assertFalse(dry_run["verified"])

        applied = plane_workflow.delete_unstarted_work_package(
            client, route, self.plan, apply=True
        )
        self.assertTrue(applied["verified"])
        self.assertEqual({}, objects)
        self.assertEqual("planned", module["status"])
        absent = plane_workflow.delete_unstarted_work_package(
            client, route, self.plan, apply=False
        )
        self.assertTrue(absent["already_absent"])
        self.assertTrue(absent["verified"])

    def test_delete_unstarted_work_package_refuses_progress_or_evidence(self) -> None:
        route, client, _, _, _, phases, _ = self._unstarted_delete_fixture()
        phases[0]["state"] = "started"
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "refuses started"):
            plane_workflow.delete_unstarted_work_package(
                client, route, self.plan, apply=False
            )

        phases[0]["state"] = "backlog"
        phases[0]["description_html"] = phases[0]["description_html"].replace(
            'data-checked="false"', 'data-checked="true"', 1
        ).replace(
            '<input type="checkbox">', '<input type="checkbox" checked="">', 1
        )
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "checklist or actual evidence"):
            plane_workflow.delete_unstarted_work_package(
                client, route, self.plan, apply=False
            )

    def test_retire_empty_module_is_guarded_and_idempotent(self) -> None:
        route = {
            "workspace": "platform",
            "project_id": "project-id",
            "project_identifier": "DCP",
            "project_name": "Delivery",
            "external_source": "delivery-v1",
        }
        module = {
            "id": "module-id",
            "name": "REQ-OLD · Old delivery boundary",
            "description": "Old delivery boundary.",
            "status": "planned",
            "external_source": "delivery-v1",
            "external_id": "module:REQ-OLD",
        }

        class FakeClient:
            project_prefix = "projects/project-id"

            def project(self) -> dict:
                return {
                    "id": "project-id",
                    "identifier": "DCP",
                    "name": "Delivery",
                    "external_source": "delivery-v1",
                    "archived_at": None,
                }

            def modules(self) -> list[dict]:
                return [module]

            def retrieve_module(self, module_id: str) -> dict:
                self._require(module_id == module["id"])
                return module

            def module_work_items(self, module_id: str) -> list[dict]:
                self._require(module_id == module["id"])
                return []

            @staticmethod
            def _require(condition: bool) -> None:
                if not condition:
                    raise AssertionError("unexpected fake client lookup")

            def request(self, method: str, suffix: str, *, params=None, data=None):
                self._require(method == "PATCH")
                self._require(suffix.endswith("/modules/module-id"))
                module.update(data)
                return module

        client = FakeClient()
        arguments = {
            "successor": "REQ-NEW",
            "reason": "The work packages moved to the grouped requirement.",
        }
        dry_run = plane_workflow.retire_empty_module(
            client, route, "REQ-OLD", apply=False, **arguments
        )
        self.assertFalse(dry_run["verified"])
        self.assertEqual("planned", module["status"])

        applied = plane_workflow.retire_empty_module(
            client, route, "REQ-OLD", apply=True, **arguments
        )
        self.assertTrue(applied["verified"])
        self.assertEqual("cancelled", module["status"])
        self.assertIn("[已取代]", module["name"])

        idempotent = plane_workflow.retire_empty_module(
            client, route, "REQ-OLD", apply=False, **arguments
        )
        self.assertTrue(idempotent["verified"])
        self.assertIsNone(idempotent["action"])

    def test_retire_empty_module_refuses_membership(self) -> None:
        route, client, _, _, _, _, _ = self._unstarted_delete_fixture()
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "non-empty"):
            plane_workflow.retire_empty_module(
                client,
                route,
                "REQ-001",
                successor="REQ-NEW",
                reason="The work packages moved to the grouped requirement.",
                apply=False,
            )

    def _legacy_fixture(self, *, all_done: bool = False):
        route = {
            "workspace": "platform",
            "project_id": "project-id",
            "project_identifier": "DCP",
            "project_name": "Delivery",
            "external_source": "delivery-v1",
        }
        current = plane_workflow.render_phase_html(self.plan["phases"][0])
        completed_html = current.replace(
            'data-checked="false"', 'data-checked="true"'
        ).replace(
            '<input type="checkbox">', '<input type="checkbox" checked="">'
        ).replace(
            "<h3>证据</h3><p>待本 Phase 完成后回填真实测试与运行证据。</p>",
            "<h3>实际证据</h3><p>targeted test and usage pass completed with recorded evidence.</p>",
        )
        module = {
            "id": "module-id",
            "name": "REQ-001 · Legacy module",
            "description": "Legacy module description.",
            "external_source": "delivery-v1",
            "external_id": "module:REQ-001",
            "status": "planned",
        }
        requirement = {
            "id": "requirement-id",
            "name": "REQ-001 · Legacy requirement",
            "description_html": "<h3>目标</h3><p>Legacy requirement.</p>",
            "external_source": "delivery-v1",
            "external_id": "requirement:REQ-001",
            "parent": None,
            "state": "done" if all_done else "ready",
        }
        work_package = {
            "id": "wp-id",
            "name": "WP-01A · Legacy delivery",
            "description_html": "<h3>目标</h3><p>Legacy delivery.</p>",
            "external_source": "delivery-v1",
            "external_id": "work-package:WP-01A",
            "parent": requirement["id"],
            "state": "done" if all_done else "started",
        }
        phases = [
            {
                "id": "phase-0",
                "name": "Phase 0 · Done",
                "description_html": completed_html,
                "external_source": "delivery-v1",
                "external_id": "phase:WP-01A:0",
                "parent": work_package["id"],
                "state": "done",
            },
            {
                "id": "phase-1",
                "name": "Phase 1 · Remaining",
                "description_html": completed_html if all_done else current,
                "external_source": "delivery-v1",
                "external_id": "phase:WP-01A:1",
                "parent": work_package["id"],
                "state": "done" if all_done else "blocked",
            },
        ]
        objects = {
            item["id"]: item for item in [requirement, work_package, *phases]
        }

        class FakeClient:
            project_prefix = "projects/project-id"

            def project(self) -> dict:
                return {
                    "id": "project-id",
                    "identifier": "DCP",
                    "name": "Delivery",
                    "external_source": "delivery-v1",
                    "archived_at": None,
                }

            def states(self) -> list[dict]:
                return [
                    {"id": "ready", "name": "Ready", "group": "unstarted"},
                    {"id": "started", "name": "In Progress", "group": "started"},
                    {"id": "blocked", "name": "Blocked", "group": "started"},
                    {"id": "done", "name": "Done", "group": "completed"},
                    {"id": "cancelled", "name": "Cancelled", "group": "cancelled"},
                ]

            def modules(self) -> list[dict]:
                return [module]

            def retrieve_module(self, module_id: str) -> dict:
                self._require(module_id == module["id"])
                return module

            def work_items(self) -> list[dict]:
                return list(objects.values())

            def retrieve_work_item(self, item_id: str) -> dict:
                return objects[item_id]

            def module_work_items(self, module_id: str) -> list[dict]:
                self._require(module_id == module["id"])
                return [{"id": item_id} for item_id in objects]

            @staticmethod
            def _require(condition: bool) -> None:
                if not condition:
                    raise AssertionError("unexpected fake client lookup")

            def request(self, method: str, suffix: str, *, params=None, data=None):
                self._require(method == "PATCH")
                item_id = suffix.rsplit("/", 1)[1]
                target = module if "/modules/" in suffix else objects[item_id]
                target.update(data)
                return target

        return route, FakeClient(), module, requirement, work_package, phases

    def test_mark_superseded_preserves_done_and_cancels_only_unfinished(self) -> None:
        route, client, module, requirement, work_package, phases = self._legacy_fixture()
        original_done_html = phases[0]["description_html"]
        dry_run = plane_workflow.mark_legacy_work_package(
            client,
            route,
            "WP-01A",
            mode="superseded",
            successor="REQ-002 / WP-02A",
            reason="The product boundary moved to the successor requirement.",
            apply=False,
        )
        self.assertEqual(1, dry_run["preserved_done_phase_count"])
        self.assertEqual(1, dry_run["cancelled_phase_count"])
        self.assertEqual("blocked", phases[1]["state"])

        applied = plane_workflow.mark_legacy_work_package(
            client,
            route,
            "WP-01A",
            mode="superseded",
            successor="REQ-002 / WP-02A",
            reason="The product boundary moved to the successor requirement.",
            apply=True,
        )
        self.assertTrue(applied["verified"])
        self.assertEqual("done", phases[0]["state"])
        self.assertEqual(original_done_html, phases[0]["description_html"])
        self.assertEqual("cancelled", phases[1]["state"])
        self.assertEqual("cancelled", work_package["state"])
        self.assertEqual("cancelled", requirement["state"])
        self.assertEqual("cancelled", module["status"])
        self.assertIn("[已取代]", work_package["name"])
        self.assertIn("plane-workflow:legacy:superseded:REQ-002/WP-02A", work_package["description_html"])

        idempotent = plane_workflow.mark_legacy_work_package(
            client,
            route,
            "WP-01A",
            mode="superseded",
            successor="REQ-002 / WP-02A",
            reason="The product boundary moved to the successor requirement.",
            apply=False,
        )
        self.assertEqual([], idempotent["actions"])
        self.assertTrue(idempotent["verified"])

    def test_mark_legacy_rejects_phase_membership_in_a_second_module(self) -> None:
        route, client, module, _, _, phases = self._legacy_fixture()
        second_module = {
            "id": "second-module-id",
            "name": "REQ-999 · Conflicting module",
            "external_source": "delivery-v1",
            "external_id": "module:REQ-999",
            "status": "planned",
        }
        original_module_work_items = client.module_work_items
        client.modules = lambda: [module, second_module]

        def module_work_items(module_id: str) -> list[dict]:
            if module_id == second_module["id"]:
                return [{"id": phases[0]["id"]}]
            return original_module_work_items(module_id)

        client.module_work_items = module_work_items
        with self.assertRaisesRegex(
            plane_workflow.WorkflowError,
            "hierarchy belongs to more than one Module",
        ):
            plane_workflow.mark_legacy_work_package(
                client,
                route,
                "WP-01A",
                mode="superseded",
                successor="REQ-002 / WP-02A",
                reason="The product boundary moved to the successor requirement.",
                apply=False,
            )

    def test_mark_historical_requires_and_preserves_complete_hierarchy(self) -> None:
        route, client, module, requirement, work_package, phases = self._legacy_fixture(
            all_done=True
        )
        phases[1]["description_html"] = phases[1]["description_html"].replace(
            "<h3>实际证据</h3>", "<h3>证据</h3>"
        )
        retained_html = phases[1]["description_html"]
        applied = plane_workflow.mark_legacy_work_package(
            client,
            route,
            "WP-01A",
            mode="historical",
            successor="REQ-002 / WP-02A",
            reason="The completed foundation remains evidence for the successor design.",
            apply=True,
        )
        self.assertTrue(applied["verified"])
        self.assertEqual(2, applied["preserved_done_phase_count"])
        self.assertEqual(0, applied["cancelled_phase_count"])
        self.assertEqual("completed", module["status"])
        self.assertEqual("done", requirement["state"])
        self.assertEqual("done", work_package["state"])
        self.assertTrue(all(phase["state"] == "done" for phase in phases))
        self.assertEqual(retained_html, phases[1]["description_html"])
        self.assertIn("[历史已完成]", module["name"])

        phases[1]["state"] = "blocked"
        with self.assertRaisesRegex(plane_workflow.WorkflowError, "requires a completed"):
            plane_workflow.mark_legacy_work_package(
                client,
                route,
                "WP-01A",
                mode="historical",
                successor="REQ-002 / WP-02A",
                reason="The completed foundation remains evidence for the successor design.",
                apply=False,
            )


if __name__ == "__main__":
    unittest.main()
