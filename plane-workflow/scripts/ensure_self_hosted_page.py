#!/usr/bin/env python3
"""Inspect or reconcile a Plane project Page through the in-cluster serializer."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import subprocess
import sys
from pathlib import Path


RESULT_PREFIX = "PLANE_PAGE_HELPER_RESULT="

REMOTE_SCRIPT = r'''
import base64
import hashlib
import json

from django.db import transaction

from plane.app.serializers.page import PageDetailSerializer, PageSerializer
from plane.app.views.page.base import page_transaction
from plane.db.models import Page, Project, WorkspaceMember

RESULT_PREFIX = "PLANE_PAGE_HELPER_RESULT="
config = json.loads(base64.b64decode("__PAYLOAD__").decode("utf-8"))


def html_sha256(value):
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def page_result(page, include_html=False):
    description_html = page.description_html or ""
    result = {
        "page_id": str(page.id),
        "name": page.name,
        "external_source": page.external_source or "",
        "external_id": page.external_id or "",
        "access": page.access,
        "is_locked": page.is_locked,
        "archived_at": page.archived_at.isoformat() if page.archived_at else None,
        "created_by_id": (
            str(page.created_by_id) if getattr(page, "created_by_id", None) else None
        ),
        "updated_by_id": (
            str(page.updated_by_id) if getattr(page, "updated_by_id", None) else None
        ),
        "description_html_length": len(description_html),
        "description_html_sha256": html_sha256(description_html),
    }
    if include_html:
        result["description_html_base64"] = base64.b64encode(
            description_html.encode("utf-8")
        ).decode("ascii")
    return result


def emit(status, verified, code=0, **values):
    payload = {"status": status, "verified": verified, **values}
    print(RESULT_PREFIX + json.dumps(payload, ensure_ascii=False))
    raise SystemExit(code)


def lock_project_pages(project):
    locked_project = Project.objects.select_for_update().get(
        pk=project.id,
        workspace__slug=project.workspace.slug,
    )
    page_ids = [
        page.id
        for page in Page.objects.filter(
            workspace=locked_project.workspace,
            projects=locked_project,
            deleted_at__isnull=True,
        ).distinct().order_by("id")
    ]
    if not page_ids:
        return locked_project, []
    locked_candidates = list(
        Page.objects.select_for_update().filter(pk__in=page_ids).order_by("id")
    )
    current_page_ids = {
        page.id
        for page in Page.objects.filter(
            workspace=locked_project.workspace,
            projects=locked_project,
            deleted_at__isnull=True,
        ).distinct().order_by("id")
    }
    locked_pages = [
        page for page in locked_candidates if page.id in current_page_ids
    ]
    return locked_project, locked_pages


project = Project.objects.get(
    pk=config["project_id"], workspace__slug=config["workspace"]
)
pages = Page.objects.filter(
    workspace=project.workspace,
    projects=project,
    deleted_at__isnull=True,
).distinct()

owner = None
if config["apply"]:
    owner_membership = WorkspaceMember.objects.filter(
        workspace=project.workspace,
        member_id=config["owner_id"],
        is_active=True,
    ).first()
    owner = owner_membership.member if owner_membership is not None else None
    if owner is None or not getattr(owner, "is_active", False):
        emit(
            "owner_not_active_workspace_member",
            False,
            code=4,
            project_id=str(project.id),
            workspace=project.workspace.slug,
            owner_id=config["owner_id"],
        )

if config["operation"] == "list":
    listed_pages = [page_result(page) for page in pages.order_by("name", "id")]
    emit(
        "listed",
        True,
        project_id=str(project.id),
        workspace=project.workspace.slug,
        count=len(listed_pages),
        pages=listed_pages,
    )


selectors = {}
ambiguous = {}
missing = []

if config["page_id"]:
    matches = pages.filter(pk=config["page_id"])
    count = matches.count()
    if count == 1:
        selectors["page_id"] = matches.first()
    elif count == 0:
        missing.append("page_id")
    else:
        ambiguous["page_id"] = count

if config["external_id"]:
    matches = pages.filter(
        external_source=config["external_source"],
        external_id=config["external_id"],
    )
    count = matches.count()
    if count == 1:
        selectors["external_identity"] = matches.first()
    elif count == 0:
        missing.append("external_identity")
    else:
        ambiguous["external_identity"] = count

if config["name"]:
    matches = pages.filter(name=config["name"])
    count = matches.count()
    if count == 1:
        selectors["name"] = matches.first()
    elif count == 0:
        missing.append("name")
    else:
        ambiguous["name"] = count

if ambiguous:
    emit(
        "ambiguous",
        False,
        code=4,
        project_id=str(project.id),
        workspace=project.workspace.slug,
        ambiguous_selectors=ambiguous,
    )

candidate_ids = {str(page.id) for page in selectors.values()}
candidate = next(iter(selectors.values()), None)
conflicting_missing = [
    selector
    for selector in missing
    if not (
        selector == "external_identity"
        and candidate is not None
        and (candidate.external_source or "", candidate.external_id or "") == ("", "")
    )
]
if len(candidate_ids) > 1 or (selectors and conflicting_missing):
    emit(
        "identity_conflict",
        False,
        code=4,
        project_id=str(project.id),
        workspace=project.workspace.slug,
        matched_selectors={key: str(value.id) for key, value in selectors.items()},
        missing_selectors=conflicting_missing,
    )

page = candidate
identity_update_required = False
if page is not None and config["external_id"]:
    requested_identity = (config["external_source"], config["external_id"])
    existing_identity = (page.external_source or "", page.external_id or "")
    if existing_identity != requested_identity:
        if existing_identity != ("", ""):
            emit(
                "identity_conflict",
                False,
                code=4,
                project_id=str(project.id),
                workspace=project.workspace.slug,
                requested_external_source=config["external_source"],
                requested_external_id=config["external_id"],
                page=page_result(page),
            )
        identity_update_required = True

if page is None:
    if not config["apply"]:
        emit(
            "missing",
            False,
            code=3,
            project_id=str(project.id),
            workspace=project.workspace.slug,
            name=config["name"],
            external_source=config["external_source"],
            external_id=config["external_id"],
        )
    if config["page_id"] or not config["name"]:
        emit(
            "missing_not_creatable",
            False,
            code=3,
            project_id=str(project.id),
            workspace=project.workspace.slug,
        )

    page_data = {
        "name": config["name"],
        "access": config["access"],
        "color": config["color"],
        "is_locked": config["is_locked"],
    }
    with transaction.atomic():
        project, locked_pages = lock_project_pages(project)
        concurrent_conflicts = []
        if config["name"] and any(
            candidate.name == config["name"] for candidate in locked_pages
        ):
            concurrent_conflicts.append("name")
        if config["external_id"] and any(
            (candidate.external_source or "") == config["external_source"]
            and (candidate.external_id or "") == config["external_id"]
            for candidate in locked_pages
        ):
            concurrent_conflicts.append("external_identity")
        if concurrent_conflicts:
            emit(
                "identity_conflict",
                False,
                code=4,
                project_id=str(project.id),
                workspace=project.workspace.slug,
                concurrent_conflicts=concurrent_conflicts,
            )
        serializer = PageSerializer(
            data=page_data,
            context={
                "project_id": project.id,
                "owned_by_id": owner.id,
                "description_json": {},
                "description_binary": None,
                "description_html": config["description_html"],
            },
        )
        serializer.is_valid(raise_exception=True)
        page = serializer.save(created_by=owner, updated_by=owner)
        persisted_html = page.description_html or ""
        if (
            config["has_description_html"]
            and persisted_html != config["description_html"]
        ):
            emit(
                "serializer_normalization_conflict",
                False,
                code=5,
                project_id=str(project.id),
                workspace=project.workspace.slug,
                requested_description_html_length=len(config["description_html"]),
                requested_description_html_sha256=html_sha256(
                    config["description_html"]
                ),
                persisted_description_html_length=len(persisted_html),
                persisted_description_html_sha256=html_sha256(persisted_html),
                page=page_result(page, config["include_html"]),
            )
        if config["external_id"]:
            page.external_source = config["external_source"]
            page.external_id = config["external_id"]
            page.save(update_fields=["external_source", "external_id"])
    status = "created"
    transaction_queued = None
else:
    current_html = page.description_html or ""
    requested_html = config["description_html"]
    content_change_required = (
        config["has_description_html"] and current_html != requested_html
    )

    if (content_change_required or identity_update_required) and page.is_locked:
        emit(
            "locked",
            False,
            code=4,
            project_id=str(project.id),
            workspace=project.workspace.slug,
            requested_description_html_sha256=(
                html_sha256(requested_html) if config["has_description_html"] else None
            ),
            requested_description_html_length=(
                len(requested_html) if config["has_description_html"] else None
            ),
            page=page_result(page, config["include_html"]),
        )

    if not config["apply"]:
        status = "would_update" if (
            content_change_required or identity_update_required
        ) else "existing"
        emit(
            status,
            status == "existing",
            project_id=str(project.id),
            workspace=project.workspace.slug,
            changed=content_change_required,
            identity_update_required=identity_update_required,
            requested_description_html_length=(
                len(requested_html) if config["has_description_html"] else None
            ),
            requested_description_html_sha256=(
                html_sha256(requested_html) if config["has_description_html"] else None
            ),
            page=page_result(page, config["include_html"]),
        )

    persisted_html = current_html
    with transaction.atomic():
        project, locked_pages = lock_project_pages(project)
        target_pages = [
            candidate for candidate in locked_pages if str(candidate.id) == str(page.id)
        ]
        if len(target_pages) != 1:
            emit(
                "identity_conflict",
                False,
                code=4,
                project_id=str(project.id),
                workspace=project.workspace.slug,
                concurrent_conflicts=["page_id"],
            )
        page = target_pages[0]

        concurrent_conflicts = []
        if config["name"]:
            matches = [
                candidate for candidate in locked_pages
                if candidate.name == config["name"]
            ]
            if len(matches) != 1 or str(matches[0].id) != str(page.id):
                concurrent_conflicts.append("name")
        if config["external_id"]:
            matches = [
                candidate for candidate in locked_pages
                if (candidate.external_source or "") == config["external_source"]
                and (candidate.external_id or "") == config["external_id"]
            ]
            match_count = len(matches)
            existing_identity = (page.external_source or "", page.external_id or "")
            external_match = (
                match_count == 1 and str(matches[0].id) == str(page.id)
            )
            if not external_match and (
                match_count != 0 or existing_identity != ("", "")
            ):
                concurrent_conflicts.append("external_identity")
            identity_update_required = not external_match
        if concurrent_conflicts:
            emit(
                "identity_conflict",
                False,
                code=4,
                project_id=str(project.id),
                workspace=project.workspace.slug,
                concurrent_conflicts=concurrent_conflicts,
                page=page_result(page),
            )

        current_html = page.description_html or ""
        content_change_required = (
            config["has_description_html"] and current_html != requested_html
        )
        if page.is_locked:
            emit(
                "locked",
                False,
                code=4,
                project_id=str(project.id),
                workspace=project.workspace.slug,
                requested_description_html_sha256=(
                    html_sha256(requested_html)
                    if config["has_description_html"]
                    else None
                ),
                requested_description_html_length=(
                    len(requested_html) if config["has_description_html"] else None
                ),
                page=page_result(page, config["include_html"]),
            )

        if content_change_required:
            serializer = PageDetailSerializer(
                page,
                data={"description_html": requested_html},
                partial=True,
            )
            serializer.is_valid(raise_exception=True)
            page = serializer.save(updated_by=owner)
            persisted_html = page.description_html or ""
            if persisted_html != requested_html:
                emit(
                    "serializer_normalization_conflict",
                    False,
                    code=5,
                    project_id=str(project.id),
                    workspace=project.workspace.slug,
                    requested_description_html_length=len(requested_html),
                    requested_description_html_sha256=html_sha256(requested_html),
                    persisted_description_html_length=len(persisted_html),
                    persisted_description_html_sha256=html_sha256(persisted_html),
                    page=page_result(page, config["include_html"]),
                )
        if identity_update_required:
            page.external_source = config["external_source"]
            page.external_id = config["external_id"]
            page.updated_by = owner
            page.save(
                update_fields=["external_source", "external_id", "updated_by", "updated_at"]
            )

    transaction_queued = None
    if content_change_required:
        try:
            page_transaction.delay(
                new_description_html=persisted_html,
                old_description_html=current_html,
                page_id=str(page.id),
            )
            transaction_queued = True
        except Exception as error:
            reread_error_type = None
            reread_verified = False
            try:
                refreshed = Page.objects.get(
                    pk=page.id,
                    workspace=project.workspace,
                    projects=project,
                    deleted_at__isnull=True,
                )
                reread_verified = (
                    html_sha256(refreshed.description_html or "")
                    == html_sha256(requested_html)
                )
            except Exception as reread_error:
                refreshed = page
                reread_error_type = type(reread_error).__name__
            emit(
                "updated_transaction_enqueue_failed",
                False,
                code=6,
                project_id=str(project.id),
                workspace=project.workspace.slug,
                changed=True,
                transaction_queued=False,
                transaction_error_type=type(error).__name__,
                post_save_reread_verified=reread_verified,
                post_save_reread_error_type=reread_error_type,
                requested_description_html_sha256=html_sha256(requested_html),
                page=page_result(refreshed, config["include_html"]),
            )
    status = "updated" if (
        content_change_required or identity_update_required
    ) else "existing"

refreshed = Page.objects.get(
    pk=page.id,
    workspace=project.workspace,
    projects=project,
    deleted_at__isnull=True,
)
verification_pages = Page.objects.filter(
    workspace=project.workspace,
    projects=project,
    deleted_at__isnull=True,
).distinct()
identity_verified = (
    not config["external_id"]
    or (
        verification_pages.filter(
            external_source=config["external_source"],
            external_id=config["external_id"],
        ).count()
        == 1
        and (refreshed.external_source or "") == config["external_source"]
        and (refreshed.external_id or "") == config["external_id"]
    )
)
name_verified = (
    not config["name"]
    or (
        verification_pages.filter(name=config["name"]).count() == 1
        and refreshed.name == config["name"]
    )
)
html_verified = (
    not config["has_description_html"]
    or html_sha256(refreshed.description_html or "")
    == html_sha256(config["description_html"])
)
verified = identity_verified and name_verified and html_verified
emit(
    status,
    verified,
    code=0 if verified else 5,
    project_id=str(project.id),
    workspace=project.workspace.slug,
    changed=(status in ("created", "updated")),
    transaction_queued=transaction_queued,
    requested_description_html_sha256=(
        html_sha256(config["description_html"])
        if config["has_description_html"]
        else None
    ),
    page=page_result(refreshed, config["include_html"]),
)
'''


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List, inspect, create, or update a Plane project Page through the API pod "
            "when the self-hosted public /api/v1 Page endpoint returns 404."
        )
    )
    parser.add_argument("--context", required=True, help="kubectl context")
    parser.add_argument("--namespace", required=True, help="Plane namespace")
    parser.add_argument(
        "--target", required=True, help="kubectl exec target, e.g. deploy/plane-api-wl"
    )
    parser.add_argument("--workspace", required=True, help="Plane workspace slug")
    parser.add_argument("--project-id", required=True, help="Plane project UUID")
    parser.add_argument("--owner-id", help="Plane user UUID; required for --apply")
    parser.add_argument("--list", action="store_true", help="List project Pages read-only")
    parser.add_argument("--page-id", help="Exact Page UUID")
    parser.add_argument("--name", help="Exact Page name")
    parser.add_argument(
        "--html-file", type=Path, help="Candidate UTF-8 HTML for dry-run or apply"
    )
    parser.add_argument(
        "--export-html", type=Path, help="Write inspected HTML to a new local file"
    )
    parser.add_argument("--access", type=int, choices=(0, 1), default=0)
    parser.add_argument("--color", default="#0F766E")
    parser.add_argument("--locked", action="store_true")
    parser.add_argument("--external-source")
    parser.add_argument("--external-id")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply", action="store_true", help="Apply one exact create or update"
    )
    mode.add_argument(
        "--check-only", action="store_true", help="Explicit alias for read-only mode"
    )
    parser.add_argument(
        "--manage-py", default="manage.py", help="manage.py path inside the API container"
    )
    return parser.parse_args(argv)


def read_html(path: Path | None) -> tuple[bool, str]:
    if path is None:
        return False, ""
    try:
        value = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ValueError(f"cannot read {path}: {error}") from error
    value = value.rstrip("\r\n")
    if not value.strip():
        raise ValueError("HTML input must not be empty")
    return True, value


def extract_result(stdout: str) -> tuple[dict, str]:
    result_lines = [
        line[len(RESULT_PREFIX) :]
        for line in stdout.splitlines()
        if line.startswith(RESULT_PREFIX)
    ]
    if len(result_lines) != 1:
        raise ValueError(f"expected one helper result, received {len(result_lines)}")
    try:
        result = json.loads(result_lines[0])
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid helper result JSON: {error}") from error
    other_output = "\n".join(
        line for line in stdout.splitlines() if not line.startswith(RESULT_PREFIX)
    )
    return result, other_output


def export_html(result: dict, path: Path) -> None:
    page = result.get("page")
    encoded = page.pop("description_html_base64", None) if isinstance(page, dict) else None
    if not isinstance(encoded, str):
        raise ValueError("helper result did not contain exported Page HTML")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("helper returned invalid base64 Page HTML") from error
    expected_hash = page.get("description_html_sha256")
    if not isinstance(expected_hash, str) or hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError("exported Page HTML did not match the reported SHA-256")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("exported Page HTML was not valid UTF-8") from error
    if len(text) != page.get("description_html_length"):
        raise ValueError("exported Page HTML did not match the reported length")
    try:
        with path.open("xb") as output:
            output.write(raw)
    except OSError as error:
        raise ValueError(f"cannot create export {path}: {error}") from error


def print_diagnostic_summary(label: str, value: str) -> None:
    if not value:
        return
    encoded = value.encode("utf-8", errors="replace")
    print(
        f"{label}: {len(value.splitlines())} line(s), {len(encoded)} bytes, "
        f"sha256={hashlib.sha256(encoded).hexdigest()}; content withheld",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if bool(args.external_source) != bool(args.external_id):
        print("--external-source and --external-id must be provided together", file=sys.stderr)
        return 2
    selectors_present = bool(args.page_id or args.name or args.external_id)
    if args.list:
        if selectors_present or args.html_file or args.export_html or args.apply:
            print("--list cannot be combined with selectors, HTML, export, or --apply", file=sys.stderr)
            return 2
    elif not selectors_present:
        print("provide --page-id, --name, or an external identity", file=sys.stderr)
        return 2
    if args.apply and args.owner_id is None:
        print("--owner-id is required with --apply", file=sys.stderr)
        return 2
    if args.apply and args.html_file is None:
        print("--html-file is required with --apply", file=sys.stderr)
        return 2
    if args.export_html and args.export_html.exists():
        print(f"export target already exists: {args.export_html}", file=sys.stderr)
        return 2

    try:
        has_description_html, description_html = read_html(args.html_file)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    payload = {
        "operation": "list" if args.list else "reconcile",
        "workspace": args.workspace,
        "project_id": args.project_id,
        "owner_id": args.owner_id,
        "page_id": args.page_id,
        "name": args.name,
        "description_html": description_html,
        "has_description_html": has_description_html,
        "include_html": args.export_html is not None,
        "access": args.access,
        "color": args.color,
        "is_locked": args.locked,
        "external_source": args.external_source,
        "external_id": args.external_id,
        "apply": args.apply,
    }
    encoded = base64.b64encode(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    remote_script = REMOTE_SCRIPT.replace("__PAYLOAD__", encoded)
    command = [
        "kubectl",
        "--context",
        args.context,
        "-n",
        args.namespace,
        "exec",
        "-i",
        args.target,
        "--",
        "python",
        args.manage_py,
        "shell",
    ]
    completed = subprocess.run(
        command,
        input=remote_script,
        text=True,
        check=False,
        capture_output=True,
    )
    try:
        result, other_output = extract_result(completed.stdout)
    except ValueError as error:
        print_diagnostic_summary("remote stdout", completed.stdout)
        print_diagnostic_summary("remote stderr", completed.stderr)
        print(str(error), file=sys.stderr)
        return completed.returncode or 1

    try:
        if args.export_html:
            export_html(result, args.export_html)
            result["exported_html"] = str(args.export_html)
    except ValueError as error:
        print_diagnostic_summary("remote non-result stdout", other_output)
        print_diagnostic_summary("remote stderr", completed.stderr)
        print(str(error), file=sys.stderr)
        return completed.returncode or 1

    print_diagnostic_summary("remote non-result stdout", other_output)
    print_diagnostic_summary("remote stderr", completed.stderr)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
