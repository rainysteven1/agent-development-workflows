#!/usr/bin/env python3
"""Behavior tests for the in-cluster Page reconciliation program."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest import mock


SCRIPT_PATH = Path(__file__).with_name("ensure_self_hosted_page.py")
SPEC = importlib.util.spec_from_file_location("ensure_self_hosted_page_contract", SCRIPT_PATH)
assert SPEC and SPEC.loader
helper = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = helper
SPEC.loader.exec_module(helper)


@dataclass
class FakeWorkspace:
    slug: str = "platform"


class FakePage:
    def __init__(
        self,
        page_id: str,
        name: str,
        project: object,
        description_html: str = "<p>old</p>",
        external_source: str = "delivery-v1",
        external_id: str = "page:decision",
        is_locked: bool = False,
    ) -> None:
        self.id = page_id
        self.name = name
        self.project = project
        self.workspace = project.workspace
        self.description_html = description_html
        self.external_source = external_source
        self.external_id = external_id
        self.access = 0
        self.color = "#0F766E"
        self.is_locked = is_locked
        self.archived_at = None
        self.deleted_at = None
        self.updated_by = None

    def save(self, update_fields: list[str] | None = None) -> None:
        del update_fields


class FakeQuerySet:
    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages

    def filter(self, **filters: object) -> "FakeQuerySet":
        def matches(page: FakePage) -> bool:
            for key, value in filters.items():
                if key == "pk" and str(page.id) != str(value):
                    return False
                if key == "pk__in" and page.id not in value:
                    return False
                if key == "workspace" and page.workspace is not value:
                    return False
                if key == "projects" and page.project is not value:
                    return False
                if key == "deleted_at__isnull" and (page.deleted_at is None) is not value:
                    return False
                if key in {"name", "external_source", "external_id"}:
                    if getattr(page, key) != value:
                        return False
            return True

        return FakeQuerySet([page for page in self.pages if matches(page)])

    def distinct(self) -> "FakeQuerySet":
        return self

    def __iter__(self):
        return iter(self.pages)

    def order_by(self, *fields: str) -> list[FakePage]:
        return sorted(self.pages, key=lambda page: tuple(str(getattr(page, f)) for f in fields))

    def count(self) -> int:
        return len(self.pages)

    def first(self) -> FakePage | None:
        return self.pages[0] if self.pages else None

    def get(self, **filters: object) -> FakePage:
        matches = self.filter(**filters).pages
        if len(matches) != 1:
            raise LookupError(filters)
        return matches[0]


def package(name: str) -> types.ModuleType:
    value = types.ModuleType(name)
    value.__path__ = []
    return value


def run_remote(
    config: dict,
    pages: list[FakePage],
    *,
    before_lock: object = None,
    transaction_failure: bool = False,
    reread_failure: bool = False,
    owner_membership_active: bool = True,
    owner_user_active: bool = True,
    owner_workspace: FakeWorkspace | None = None,
    serializer_normalizer: object = None,
) -> tuple[int, dict, dict]:
    project = pages[0].project
    calls = {
        "detail_updates": 0,
        "transactions": [],
        "lock_count": 0,
        "project_lock_count": 0,
        "fail_reread": False,
    }

    class PageManager(FakeQuerySet):
        def select_for_update(self) -> "PageManager":
            calls["lock_count"] += 1
            return self

        def get(self, **filters: object) -> FakePage:
            if calls["fail_reread"]:
                raise RuntimeError("simulated post-save reread failure")
            return super().get(**filters)

    class ProjectManager:
        def select_for_update(self) -> "ProjectManager":
            calls["project_lock_count"] += 1
            if before_lock is not None:
                before_lock()
            return self

        @staticmethod
        def get(**filters: object) -> object:
            if str(filters["pk"]) != str(project.id):
                raise LookupError(filters)
            if filters["workspace__slug"] != project.workspace.slug:
                raise LookupError(filters)
            return project

    class UserManager:
        @staticmethod
        def get(pk: str) -> object:
            return types.SimpleNamespace(id=pk, is_active=True)

    owner = types.SimpleNamespace(id="owner-id", is_active=owner_user_active)
    owner_membership = types.SimpleNamespace(
        member=owner,
        member_id=owner.id,
        workspace=owner_workspace or project.workspace,
        is_active=owner_membership_active,
    )

    class WorkspaceMemberManager:
        @staticmethod
        def filter(**filters: object) -> object:
            memberships = [owner_membership]
            matches = [
                membership
                for membership in memberships
                if all(
                    (
                        key == "workspace"
                        and membership.workspace is value
                    )
                    or (
                        key == "member_id"
                        and str(membership.member_id) == str(value)
                    )
                    or (key == "is_active" and membership.is_active is value)
                    for key, value in filters.items()
                )
            ]
            return types.SimpleNamespace(
                first=lambda: matches[0] if matches else None
            )

    class PageDetailSerializer:
        def __init__(self, page: FakePage, data: dict, partial: bool) -> None:
            self.page = page
            self.data = data
            self.partial = partial

        def is_valid(self, raise_exception: bool = False) -> bool:
            del raise_exception
            return True

        def save(self, **values: object) -> FakePage:
            calls["detail_updates"] += 1
            requested = self.data["description_html"]
            self.page.description_html = (
                serializer_normalizer(requested)
                if callable(serializer_normalizer)
                else requested
            )
            self.page.updated_by = values.get("updated_by")
            return self.page

    class PageSerializer:
        def __init__(self, data: dict, context: dict) -> None:
            self.data = data
            self.context = context

        def is_valid(self, raise_exception: bool = False) -> bool:
            del raise_exception
            return True

        def save(self, **values: object) -> FakePage:
            page = FakePage(
                "created-page",
                self.data["name"],
                project,
                description_html=self.context["description_html"],
                external_source="",
                external_id="",
                is_locked=self.data["is_locked"],
            )
            page.updated_by = values.get("updated_by")
            pages.append(page)
            return page

    class PageTransaction:
        @staticmethod
        def delay(**values: object) -> None:
            calls["transactions"].append(values)
            if transaction_failure:
                calls["fail_reread"] = reread_failure
                raise RuntimeError("simulated transaction enqueue failure")

    page_model = type("Page", (), {"objects": PageManager(pages)})
    project_model = type("Project", (), {"objects": ProjectManager()})
    user_model = type("User", (), {"objects": UserManager()})
    workspace_member_model = type(
        "WorkspaceMember", (), {"objects": WorkspaceMemberManager()}
    )

    modules = {
        name: package(name)
        for name in (
            "django",
            "django.contrib",
            "django.db",
            "plane",
            "plane.app",
            "plane.app.serializers",
            "plane.app.views",
            "plane.app.views.page",
            "plane.db",
        )
    }
    modules["django.contrib.auth"] = types.ModuleType("django.contrib.auth")
    modules["django.contrib.auth"].get_user_model = lambda: user_model
    modules["django.db"].transaction = types.SimpleNamespace(
        atomic=lambda: contextlib.nullcontext()
    )
    modules["plane.app.serializers.page"] = types.ModuleType(
        "plane.app.serializers.page"
    )
    modules["plane.app.serializers.page"].PageDetailSerializer = PageDetailSerializer
    modules["plane.app.serializers.page"].PageSerializer = PageSerializer
    modules["plane.app.views.page.base"] = types.ModuleType("plane.app.views.page.base")
    modules["plane.app.views.page.base"].page_transaction = PageTransaction()
    modules["plane.db.models"] = types.ModuleType("plane.db.models")
    modules["plane.db.models"].Page = page_model
    modules["plane.db.models"].Project = project_model
    modules["plane.db.models"].WorkspaceMember = workspace_member_model

    encoded = base64.b64encode(json.dumps(config).encode("utf-8")).decode("ascii")
    remote_script = helper.REMOTE_SCRIPT.replace("__PAYLOAD__", encoded)
    stdout = io.StringIO()
    exit_code = 0
    with mock.patch.dict(sys.modules, modules), contextlib.redirect_stdout(stdout):
        try:
            exec(compile(remote_script, "<remote-page-helper>", "exec"), {})
        except SystemExit as error:
            exit_code = int(error.code or 0)
    result, _ = helper.extract_result(stdout.getvalue())
    return exit_code, result, calls


def config(**overrides: object) -> dict:
    value = {
        "operation": "reconcile",
        "workspace": "platform",
        "project_id": "project-id",
        "owner_id": "owner-id",
        "page_id": "page-1",
        "name": "Decision",
        "description_html": "<p>new</p>",
        "has_description_html": True,
        "include_html": False,
        "access": 0,
        "color": "#0F766E",
        "is_locked": False,
        "external_source": "delivery-v1",
        "external_id": "page:decision",
        "apply": True,
    }
    value.update(overrides)
    return value


class SelfHostedPageRemoteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = types.SimpleNamespace(id="project-id", workspace=FakeWorkspace())

    def test_update_uses_detail_serializer_task_and_exact_reread(self) -> None:
        page = FakePage("page-1", "Decision", self.project)
        exit_code, result, calls = run_remote(config(), [page])
        self.assertEqual(0, exit_code)
        self.assertEqual("updated", result["status"])
        self.assertTrue(result["verified"])
        self.assertEqual("<p>new</p>", page.description_html)
        self.assertEqual(1, calls["detail_updates"])
        self.assertEqual(1, len(calls["transactions"]))
        self.assertEqual(1, calls["lock_count"])
        self.assertEqual(1, calls["project_lock_count"])
        self.assertEqual("<p>new</p>", calls["transactions"][0]["new_description_html"])
        self.assertEqual(result["requested_description_html_sha256"], result["page"]["description_html_sha256"])

    def test_apply_rejects_owner_outside_active_workspace_membership(self) -> None:
        scenarios = [
            {"owner_membership_active": False},
            {"owner_user_active": False},
            {"owner_workspace": FakeWorkspace(slug="other-workspace")},
        ]
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                page = FakePage("page-1", "Decision", self.project)
                exit_code, result, calls = run_remote(
                    config(), [page], **scenario
                )
                self.assertEqual(4, exit_code)
                self.assertEqual(
                    "owner_not_active_workspace_member", result["status"]
                )
                self.assertEqual("<p>old</p>", page.description_html)
                self.assertEqual(0, calls["detail_updates"])
                self.assertEqual([], calls["transactions"])

    def test_serializer_normalization_is_rejected_before_transaction(self) -> None:
        page = FakePage("page-1", "Decision", self.project)
        exit_code, result, calls = run_remote(
            config(),
            [page],
            serializer_normalizer=lambda value: value + " ",
        )
        self.assertEqual(5, exit_code)
        self.assertEqual("serializer_normalization_conflict", result["status"])
        self.assertEqual(1, calls["detail_updates"])
        self.assertEqual([], calls["transactions"])

    def test_locked_page_rejects_update_without_side_effect(self) -> None:
        page = FakePage("page-1", "Decision", self.project, is_locked=True)
        exit_code, result, calls = run_remote(config(), [page])
        self.assertEqual(4, exit_code)
        self.assertEqual("locked", result["status"])
        self.assertEqual("<p>old</p>", page.description_html)
        self.assertEqual(0, calls["detail_updates"])
        self.assertEqual([], calls["transactions"])

    def test_locked_page_rejects_noop_apply(self) -> None:
        page = FakePage(
            "page-1",
            "Decision",
            self.project,
            description_html="<p>new</p>",
            is_locked=True,
        )
        exit_code, result, calls = run_remote(config(), [page])
        self.assertEqual(4, exit_code)
        self.assertEqual("locked", result["status"])
        self.assertEqual(0, calls["detail_updates"])
        self.assertEqual([], calls["transactions"])

    def test_locked_dry_run_reports_candidate_length_and_hash(self) -> None:
        page = FakePage("page-1", "Decision", self.project, is_locked=True)
        exit_code, result, calls = run_remote(config(apply=False), [page])
        self.assertEqual(4, exit_code)
        self.assertEqual("locked", result["status"])
        self.assertEqual(len("<p>new</p>"), result["requested_description_html_length"])
        self.assertEqual(
            hashlib.sha256(b"<p>new</p>").hexdigest(),
            result["requested_description_html_sha256"],
        )
        self.assertEqual(0, calls["project_lock_count"])

    def test_mismatched_exact_selectors_are_rejected(self) -> None:
        first = FakePage("page-1", "First", self.project)
        second = FakePage("page-2", "Decision", self.project, external_id="page:other")
        exit_code, result, calls = run_remote(config(), [first, second])
        self.assertEqual(4, exit_code)
        self.assertEqual("identity_conflict", result["status"])
        self.assertEqual(0, calls["detail_updates"])

    def test_concurrent_selector_change_is_rejected_after_row_lock(self) -> None:
        page = FakePage("page-1", "Decision", self.project)

        def rename_page() -> None:
            page.name = "Renamed concurrently"

        exit_code, result, calls = run_remote(
            config(),
            [page],
            before_lock=rename_page,
        )
        self.assertEqual(4, exit_code)
        self.assertEqual("identity_conflict", result["status"])
        self.assertEqual(["name"], result["concurrent_conflicts"])
        self.assertEqual(0, calls["detail_updates"])
        self.assertEqual([], calls["transactions"])

    def test_concurrent_external_identity_claim_blocks_adoption(self) -> None:
        target = FakePage(
            "page-1",
            "Decision",
            self.project,
            external_source="",
            external_id="",
        )
        pages = [target]

        def claim_identity() -> None:
            pages.append(
                FakePage("page-2", "Other", self.project)
            )

        exit_code, result, calls = run_remote(
            config(page_id=None),
            pages,
            before_lock=claim_identity,
        )
        self.assertEqual(4, exit_code)
        self.assertEqual("identity_conflict", result["status"])
        self.assertEqual(["external_identity"], result["concurrent_conflicts"])
        self.assertEqual("", target.external_id)
        self.assertEqual(0, calls["detail_updates"])

    def test_enqueue_and_reread_failure_still_report_applied_hash(self) -> None:
        page = FakePage("page-1", "Decision", self.project)
        exit_code, result, calls = run_remote(
            config(),
            [page],
            transaction_failure=True,
            reread_failure=True,
        )
        self.assertEqual(6, exit_code)
        self.assertEqual("updated_transaction_enqueue_failed", result["status"])
        self.assertEqual("RuntimeError", result["transaction_error_type"])
        self.assertEqual("RuntimeError", result["post_save_reread_error_type"])
        self.assertFalse(result["post_save_reread_verified"])
        self.assertEqual(
            result["requested_description_html_sha256"],
            result["page"]["description_html_sha256"],
        )
        self.assertEqual(1, calls["detail_updates"])

    def test_unclaimed_exact_name_can_receive_stable_identity(self) -> None:
        page = FakePage(
            "page-1",
            "Decision",
            self.project,
            description_html="<p>new</p>",
            external_source="",
            external_id="",
        )
        exit_code, result, calls = run_remote(
            config(page_id=None),
            [page],
        )
        self.assertEqual(0, exit_code)
        self.assertEqual("updated", result["status"])
        self.assertTrue(result["verified"])
        self.assertEqual("delivery-v1", page.external_source)
        self.assertEqual("page:decision", page.external_id)
        self.assertEqual(0, calls["detail_updates"])

    def test_missing_exact_name_is_created_and_verified(self) -> None:
        seed = FakePage("seed", "Existing", self.project)
        create_config = config(
            page_id=None,
            name="New Decision",
            external_id="page:new-decision",
        )
        exit_code, result, calls = run_remote(create_config, [seed])
        self.assertEqual(0, exit_code)
        self.assertEqual("created", result["status"])
        self.assertTrue(result["verified"])
        self.assertEqual("page:new-decision", result["page"]["external_id"])
        self.assertEqual(
            hashlib.sha256(b"<p>new</p>").hexdigest(),
            result["page"]["description_html_sha256"],
        )
        self.assertEqual(0, calls["detail_updates"])


if __name__ == "__main__":
    unittest.main()
