#!/usr/bin/env python3
"""Deterministic Plane hierarchy, inspection, and Phase transition CLI."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import http.client
import json
import os
import re
import shlex
import ssl
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable


SKILL_DIR = Path(__file__).resolve().parent.parent
PLANE_CONNECTION_FILE = Path.home() / ".config/surveying/plane.env"
WP_ID_RE = re.compile(r"^WP-\d{2}[A-Z]$")
GIT_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+$")
MERGE_REQUEST_URL_RE = re.compile(
    r"^https://[^/\s]+/.+/-/merge_requests/[1-9][0-9]*(?:[/?#].*)?$"
)
LEGACY_SUCCESSOR_RE = re.compile(r"^[A-Z][A-Z0-9-]+(?:\s*/\s*WP-\d{2}[A-Z])?$")
PRIORITIES = {"urgent", "high", "medium", "low", "none"}
COMMIT_REVIEW_MODE = "ocr"
COMMIT_REVIEW_MODEL = ""
COMMIT_REVIEW_REASONING_EFFORT = ""
COMMIT_REVIEW_MARKER_PREFIX = "plane-workflow:commit-review:v1:"
REVIEWER_SESSION_MARKER_PREFIX = "plane-workflow:reviewer-session:v1:"
HISTORY_REWRITE_MARKER_PREFIX = "plane-workflow:history-rewrite:v1:"
WP_MR_MARKER_PREFIX = "plane-workflow:wp-mr:v1:"
WP_MERGE_MARKER_PREFIX = "plane-workflow:wp-merge:v1:"
SAFE_READ_ATTEMPTS = 3
PROXY_TUNNEL_407_RE = re.compile(
    r"^Tunnel connection failed:\s*407(?:\s+Proxy Authentication Required)?\s*$",
    re.IGNORECASE,
)


class WorkflowError(RuntimeError):
    pass


class SafeReadRetryExhausted(RuntimeError):
    def __init__(self, attempts: int, cause: BaseException) -> None:
        super().__init__(str(cause))
        self.attempts = attempts
        self.cause = cause


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowError(f"cannot load JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise WorkflowError(f"{path} must contain a JSON object")
    return value


def git_root(path: Path) -> Path:
    start = path.resolve()
    if start.is_file():
        start = start.parent
    completed = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode == 0:
        return Path(completed.stdout.strip()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "AGENTS.md").is_file():
            return candidate
    raise WorkflowError(f"cannot resolve repository root from {path}")


def _require_route(route: dict[str, Any], evidence: str) -> dict[str, Any]:
    required = (
        "workspace",
        "project_id",
        "project_identifier",
        "project_name",
        "external_source",
    )
    missing = [key for key in required if not str(route.get(key, "")).strip()]
    if missing:
        raise WorkflowError(f"Plane route in {evidence} is missing: {', '.join(missing)}")
    try:
        uuid.UUID(str(route["project_id"]))
    except ValueError as error:
        raise WorkflowError(f"invalid project UUID in {evidence}") from error
    resolved = {key: str(route[key]).strip() for key in required}
    resolved.update({"schema_version": 1, "evidence": evidence})
    return resolved


def _route_from_agents(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    patterns = {
        "workspace": r"workspace\s+`([^`]+)`",
        "project_id": r"project UUID\s+`([0-9a-fA-F-]{36})`",
        "project": r"project\s+`([^`]+)`\s+\(`([^`]+)`\)",
        "external_source": r"external source\s+`([^`]+)`",
    }
    workspace = re.search(patterns["workspace"], text, re.IGNORECASE)
    project_id = re.search(patterns["project_id"], text, re.IGNORECASE)
    project = re.search(patterns["project"], text, re.IGNORECASE)
    source = re.search(patterns["external_source"], text, re.IGNORECASE)
    if not all((workspace, project_id, project, source)):
        return None
    assert workspace and project_id and project and source
    return {
        "workspace": workspace.group(1),
        "project_id": project_id.group(1),
        "project_identifier": project.group(1),
        "project_name": project.group(2),
        "external_source": source.group(1),
    }


def resolve_route(repo: Path) -> dict[str, Any]:
    root = git_root(repo)
    start = repo.resolve()
    if start.is_file():
        start = start.parent
    candidates = [start]
    candidates.extend(parent for parent in start.parents if parent == root or root in parent.parents)
    route: dict[str, Any] | None = None
    for candidate in candidates:
        route_file = candidate / ".plane-workflow.json"
        if route_file.is_file():
            route = _require_route(load_json(route_file), str(route_file))
            break
        agents_file = candidate / "AGENTS.md"
        route_data = _route_from_agents(agents_file) if agents_file.is_file() else None
        if route_data is not None:
            route = _require_route(route_data, str(agents_file))
            break
        if candidate == root:
            break
    if route is None:
        raise WorkflowError(
            "repository has no unambiguous Plane route; add .plane-workflow.json "
            "from the skill template or declare all route fields in the closest AGENTS.md"
        )
    route["repository"] = str(root)
    return route


def _nonempty(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty string")


def _date(value: Any, path: str, errors: list[str]) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        errors.append(f"{path} must be an ISO date (YYYY-MM-DD)")
        return None


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if plan.get("template") is True:
        errors.append("template is not executable; replace every example value and remove template=true")
    serialized = json.dumps(plan, ensure_ascii=False)
    for placeholder in ("CHANGE-ME", "WP-XXA", "YYYY-MM-DD"):
        if placeholder in serialized:
            errors.append(f"template placeholder remains: {placeholder}")
    for section in ("module", "requirement", "work_package"):
        if not isinstance(plan.get(section), dict):
            errors.append(f"{section} must be an object")
    if errors:
        return errors
    module = plan["module"]
    requirement = plan["requirement"]
    wp = plan["work_package"]
    for section_name, section in (("module", module), ("requirement", requirement)):
        for key in ("id", "title", "description"):
            _nonempty(section.get(key), f"{section_name}.{key}", errors)
    if module.get("id") != requirement.get("id"):
        errors.append("module.id must equal requirement.id")
    for key in ("id", "title", "goal", "scope", "acceptance"):
        _nonempty(wp.get(key), f"work_package.{key}", errors)
    if not WP_ID_RE.fullmatch(str(wp.get("id", ""))):
        errors.append("work_package.id must match WP-XXA (for example WP-01A)")
    boundaries = wp.get("boundaries")
    if not isinstance(boundaries, list) or not boundaries:
        errors.append("work_package.boundaries must be a non-empty list")
    elif any(not isinstance(item, str) or not item.strip() for item in boundaries):
        errors.append("every work_package boundary must be non-empty text")
    repositories = wp.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        errors.append("work_package.repositories must contain at least one repository slug")
    elif any(
        not isinstance(item, str) or not REPOSITORY_SLUG_RE.fullmatch(item)
        for item in repositories
    ):
        errors.append("every work_package repository must be a group/repository slug")
    elif len(set(repositories)) != len(repositories):
        errors.append("work_package.repositories must not contain duplicates")
    if wp.get("priority") not in PRIORITIES:
        errors.append(f"work_package.priority must be one of {sorted(PRIORITIES)}")
    wp_start = _date(wp.get("start_date"), "work_package.start_date", errors)
    wp_end = _date(wp.get("target_date"), "work_package.target_date", errors)
    if wp_start and wp_end and wp_start > wp_end:
        errors.append("work_package.start_date must not follow target_date")
    requirement_priority = requirement.get("priority", wp.get("priority"))
    if requirement_priority not in PRIORITIES:
        errors.append(f"requirement.priority must be one of {sorted(PRIORITIES)}")
    requirement_start = _date(
        requirement.get("start_date", wp.get("start_date")),
        "requirement.start_date",
        errors,
    )
    requirement_end = _date(
        requirement.get("target_date", wp.get("target_date")),
        "requirement.target_date",
        errors,
    )
    if requirement_start and requirement_end and requirement_start > requirement_end:
        errors.append("requirement.start_date must not follow target_date")
    if wp_start and requirement_start and wp_start < requirement_start:
        errors.append("work_package.start_date precedes Requirement start_date")
    if wp_end and requirement_end and wp_end > requirement_end:
        errors.append("work_package.target_date follows Requirement target_date")
    phases = plan.get("phases")
    if not isinstance(phases, list) or not 1 <= len(phases) <= 9:
        errors.append("phases must contain 1-9 Phase objects")
        return errors
    numbers: list[int] = []
    prior_start: dt.date | None = None
    for index, phase in enumerate(phases):
        prefix = f"phases[{index}]"
        if not isinstance(phase, dict):
            errors.append(f"{prefix} must be an object")
            continue
        number = phase.get("number")
        if not isinstance(number, int) or number < 0:
            errors.append(f"{prefix}.number must be a non-negative integer")
        else:
            numbers.append(number)
        for key in ("title", "goal", "acceptance"):
            _nonempty(phase.get(key), f"{prefix}.{key}", errors)
        tasks = phase.get("tasks")
        if not isinstance(tasks, list) or not 2 <= len(tasks) <= 5:
            errors.append(f"{prefix}.tasks must contain 2-5 items")
        elif any(not isinstance(item, str) or not item.strip() for item in tasks):
            errors.append(f"every {prefix}.tasks item must be non-empty text")
        if phase.get("priority") not in PRIORITIES:
            errors.append(f"{prefix}.priority must be one of {sorted(PRIORITIES)}")
        start = _date(phase.get("start_date"), f"{prefix}.start_date", errors)
        end = _date(phase.get("target_date"), f"{prefix}.target_date", errors)
        if start and end and start > end:
            errors.append(f"{prefix}.start_date must not follow target_date")
        if start and wp_start and start < wp_start:
            errors.append(f"{prefix}.start_date precedes Work Package start_date")
        if end and wp_end and end > wp_end:
            errors.append(f"{prefix}.target_date follows Work Package target_date")
        if start and prior_start and start < prior_start:
            errors.append(f"{prefix}.start_date must not precede the prior Phase start")
        if start:
            prior_start = start
    if numbers and numbers != list(range(len(phases))):
        errors.append("Phase numbers must be unique, ordered, and contiguous from 0")
    return errors


def checked_task_html(task: str, checked: bool = False) -> str:
    flag = "true" if checked else "false"
    checked_attr = ' checked=""' if checked else ""
    return (
        f'<li data-type="taskItem" data-checked="{flag}">'
        f'<label><input type="checkbox"{checked_attr}><span></span></label>'
        f'<div><p>{html.escape(task)}</p></div></li>'
    )


def render_wp_html(plan: dict[str, Any]) -> str:
    wp = plan["work_package"]
    boundaries = "".join(f"<li><p>{html.escape(item)}</p></li>" for item in wp["boundaries"])
    repositories = "".join(
        f"<li><code>{html.escape(item)}</code></li>" for item in sorted(wp["repositories"])
    )
    return (
        f"<h3>目标</h3><p>{html.escape(wp['goal'])}</p>"
        f"<h3>参与仓库</h3><ul>{repositories}</ul>"
        f"<h3>设计边界</h3><ul>{boundaries}</ul>"
        f"<h3>交付范围</h3><p>{html.escape(wp['scope'])}</p>"
        f"<h3>总体验收</h3><p>{html.escape(wp['acceptance'])}</p>"
    )


def render_phase_html(phase: dict[str, Any]) -> str:
    tasks = "".join(checked_task_html(task) for task in phase["tasks"])
    boundaries = phase.get("boundaries") or []
    boundary_html = ""
    if boundaries:
        items = "".join(f"<li><p>{html.escape(item)}</p></li>" for item in boundaries)
        boundary_html = f"<h3>明确边界</h3><ul>{items}</ul>"
    return (
        f"<h3>目标</h3><p>{html.escape(phase['goal'])}</p>"
        f'<h3>具体任务</h3><ul data-type="taskList">{tasks}</ul>'
        f"<h3>验收标准</h3><p>{html.escape(phase['acceptance'])}</p>"
        "<h3>证据</h3><p>待本 Phase 完成后回填真实测试与运行证据。</p>"
        f"{boundary_html}"
    )


def render_objects(plan: dict[str, Any], external_source: str | None = None) -> dict[str, Any]:
    errors = validate_plan(plan)
    if errors:
        raise WorkflowError("invalid plan:\n- " + "\n- ".join(errors))
    module = plan["module"]
    requirement = plan["requirement"]
    wp = plan["work_package"]
    source = external_source or "<repository external_source>"
    module_name = f"{module['id']} · {module['title']}"
    requirement_name = f"{requirement['id']} · {requirement['title']}"
    wp_name = f"{wp['id']} · {wp['title']}"
    objects: dict[str, Any] = {
        "module": {
            "name": module_name,
            "description": module["description"],
            "status": "planned",
            "external_source": source,
            "external_id": f"module:{requirement['id']}",
        },
        "requirement": {
            "name": requirement_name,
            "description_html": f"<h3>目标</h3><p>{html.escape(requirement['description'])}</p>",
            "priority": requirement.get("priority", wp["priority"]),
            "start_date": requirement.get("start_date", wp["start_date"]),
            "target_date": requirement.get("target_date", wp["target_date"]),
            "external_source": source,
            "external_id": f"requirement:{requirement['id']}",
        },
        "work_package": {
            "name": wp_name,
            "description_html": render_wp_html(plan),
            "priority": wp["priority"],
            "start_date": wp["start_date"],
            "target_date": wp["target_date"],
            "external_source": source,
            "external_id": f"work-package:{wp['id']}",
            "parent_external_id": f"requirement:{requirement['id']}",
            "label": wp["id"],
        },
        "phases": [],
    }
    for phase in plan["phases"]:
        objects["phases"].append(
            {
                "number": phase["number"],
                "name": f"Phase {phase['number']} · {phase['title']}",
                "description_html": render_phase_html(phase),
                "priority": phase["priority"],
                "start_date": phase["start_date"],
                "target_date": phase["target_date"],
                "external_source": source,
                "external_id": f"phase:{wp['id']}:{phase['number']}",
                "parent_external_id": f"work-package:{wp['id']}",
                "label": wp["id"],
            }
        )
    return objects


class PhaseParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tasks: list[dict[str, Any]] = []
        self.headings: list[str] = []
        self.sections: dict[str, list[str]] = {}
        self._task: dict[str, Any] | None = None
        self._heading = False
        self._heading_text: list[str] = []
        self._task_text: list[str] = []
        self._current_section: str | None = None
        self._in_code = False
        self.section_codes: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "li" and values.get("data-type") == "taskItem":
            self._task = {"data_checked": values.get("data-checked") == "true", "input_checked": False}
            self._task_text = []
        elif self._task is not None:
            if tag == "input" and values.get("type") == "checkbox":
                self._task["input_checked"] = "checked" in values
        if tag in {"h1", "h2", "h3", "h4"}:
            self._heading = True
            self._heading_text = []
        elif tag == "code":
            self._in_code = True

    def handle_endtag(self, tag: str) -> None:
        if self._task is not None and tag == "li":
            self._task["text"] = " ".join("".join(self._task_text).split())
            self.tasks.append(self._task)
            self._task = None
            self._task_text = []
        if self._heading and tag in {"h1", "h2", "h3", "h4"}:
            heading = " ".join("".join(self._heading_text).split())
            self.headings.append(heading)
            self._current_section = heading
            self.sections.setdefault(heading, [])
            self._heading = False
            self._heading_text = []
        elif tag == "code":
            self._in_code = False

    def handle_data(self, data: str) -> None:
        if self._heading:
            self._heading_text.append(data)
            return
        if self._task is not None:
            self._task_text.append(data)
        if self._current_section is not None:
            self.sections[self._current_section].append(data)
            if self._in_code:
                self.section_codes.setdefault(self._current_section, []).append(data)


def phase_summary(description_html: str) -> dict[str, Any]:
    parser = PhaseParser()
    parser.feed(description_html)
    checked = sum(
        1 for task in parser.tasks if task["data_checked"] and task["input_checked"]
    )
    partial = [
        index
        for index, task in enumerate(parser.tasks)
        if task["data_checked"] != task["input_checked"]
    ]
    current = next(
        (task["text"] for task in parser.tasks if not (task["data_checked"] and task["input_checked"])),
        None,
    )
    return {
        "checked": checked,
        "total": len(parser.tasks),
        "current": current,
        "remaining": len(parser.tasks) - checked,
        "partial_marker_indexes": partial,
        "headings": parser.headings,
        "tasks": [task["text"] for task in parser.tasks],
        "sections": {
            heading: " ".join("".join(parts).split())
            for heading, parts in parser.sections.items()
        },
        "section_codes": {
            heading: [" ".join(value.split()) for value in values if value.strip()]
            for heading, values in parser.section_codes.items()
        },
        "complete": bool(parser.tasks) and checked == len(parser.tasks) and not partial,
    }


def work_package_repositories(description_html: str) -> set[str]:
    summary = phase_summary(description_html)
    repositories = summary["section_codes"].get("参与仓库", [])
    if not repositories or any(not REPOSITORY_SLUG_RE.fullmatch(item) for item in repositories):
        raise WorkflowError("Work Package description lacks a valid 参与仓库 repository set")
    if len(set(repositories)) != len(repositories):
        raise WorkflowError("Work Package description contains duplicate participating repositories")
    return set(repositories)


def append_legacy_work_package_repositories(
    description_html: str, repositories: list[str]
) -> tuple[str, bool]:
    """Add only the missing legacy repository section; never rewrite existing WP HTML."""
    normalized = sorted(set(repositories))
    if not normalized or any(not REPOSITORY_SLUG_RE.fullmatch(item) for item in normalized):
        raise WorkflowError("legacy repository migration requires canonical repository slugs")
    summary = phase_summary(description_html)
    if "参与仓库" in summary["headings"]:
        existing = work_package_repositories(description_html)
        requested = set(normalized)
        if existing != requested:
            raise WorkflowError(
                "legacy repository migration refuses to rewrite an existing repository set"
            )
        return description_html, False
    repository_html = "".join(f"<li><code>{html.escape(item)}</code></li>" for item in normalized)
    return description_html + f"<h3>参与仓库</h3><ul>{repository_html}</ul>", True


def _evidence_section_valid(summary: dict[str, Any], heading: str) -> bool:
    evidence = str(summary.get("sections", {}).get(heading, "")).strip()
    if len(evidence) < 24:
        return False
    lowered = evidence.lower()
    placeholders = ("待本 phase", "todo", "待补充", "待回填", "planned evidence")
    if any(placeholder in lowered for placeholder in placeholders):
        return False
    if summary.get("section_codes", {}).get(heading):
        return True
    observable = re.compile(
        r"(?:\b(?:passed|failed|success|failure|observed|status|revision|digest|request[_ -]?id|http\s*\d{3}|exit\s+code|usage)\b|通过|失败|成功|观察|回读|截图|状态|版本|摘要)",
        re.IGNORECASE,
    )
    return bool(observable.search(evidence))


def completion_evidence_valid(summary: dict[str, Any]) -> bool:
    return _evidence_section_valid(summary, "实际证据")


def retained_legacy_phase_has_evidence(
    item: dict[str, Any], completed_state_id: str
) -> bool:
    """Validate retained Plane evidence without rewriting pre-harness headings."""

    summary = phase_summary(item.get("description_html") or "")
    return (
        object_id(item.get("state")) == completed_state_id
        and summary["complete"]
        and any(
            _evidence_section_valid(summary, heading)
            for heading in ("实际证据", "证据")
        )
    )


def validate_phase_completion(current_html: str, final_html: str) -> dict[str, Any]:
    current = phase_summary(current_html)
    final = phase_summary(final_html)
    if not current["tasks"]:
        raise WorkflowError("current Plane Phase has no task-list items")
    if final["tasks"] != current["tasks"]:
        raise WorkflowError("final Phase task list must exactly preserve current task count, order, and text")
    if not final["complete"]:
        raise WorkflowError(f"final Phase checklist is incomplete: {final['checked']}/{final['total']}")
    for heading in ("目标", "验收标准"):
        before = current["sections"].get(heading, "")
        after = final["sections"].get(heading, "")
        if not before or before != after:
            raise WorkflowError(f"final Phase description must preserve the current {heading} section")
    if not completion_evidence_valid(final):
        raise WorkflowError("final Phase description must contain non-placeholder 实际证据")
    current_review_markers = set(
        re.findall(
            r"plane-workflow:(?:commit-review|reviewer-session|history-rewrite):v1:[^<\s]+",
            current_html,
        )
    )
    missing_review_markers = sorted(
        marker for marker in current_review_markers if marker not in final_html
    )
    if missing_review_markers:
        raise WorkflowError("final Phase description must preserve recorded commit review evidence")
    return final


def render_ledger(plan: dict[str, Any], phase_number: int) -> str:
    errors = validate_plan(plan)
    if errors:
        raise WorkflowError("invalid plan:\n- " + "\n- ".join(errors))
    phase = next((item for item in plan["phases"] if item["number"] == phase_number), None)
    if phase is None:
        raise WorkflowError(f"Phase {phase_number} is not present in the plan")
    template = (SKILL_DIR / "assets/phase-ledger.template.md").read_text(encoding="utf-8")
    checklist = "\n".join(f"- [未开始] {task}" for task in phase["tasks"])
    values = {
        "WORK_PACKAGE_ID": plan["work_package"]["id"],
        "PHASE_NUMBER": str(phase_number),
        "PLANE_STATE": "Not Started",
        "CHECKED": "0",
        "TOTAL": str(len(phase["tasks"])),
        "CURRENT_ITEM": phase["tasks"][0],
        "REMAINING": str(len(phase["tasks"])),
        "GOAL": phase["goal"],
        "ACCEPTANCE": phase["acceptance"],
        "CHECKLIST": checklist,
        "DATE": dt.date.today().isoformat(),
    }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def _read_plane_connection_file(path: Path) -> dict[str, str]:
    try:
        path_metadata = path.lstat()
    except OSError as error:
        raise WorkflowError(f"cannot stat Plane connection file {path}: {error}") from error
    if not stat.S_ISREG(path_metadata.st_mode):
        raise WorkflowError(f"Plane connection file {path} must be a regular file")

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise WorkflowError(f"cannot open Plane connection file {path}: {error}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise WorkflowError(f"Plane connection file {path} must be a regular file")
        if metadata.st_uid != os.getuid():
            raise WorkflowError(f"Plane connection file {path} must be owned by the current user")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise WorkflowError(f"Plane connection file {path} must have mode 600 or stricter")
        with os.fdopen(descriptor, encoding="utf-8") as connection_file:
            descriptor = -1
            lines = connection_file.read().splitlines()
    except UnicodeDecodeError as error:
        raise WorkflowError(f"Plane connection file {path} must be valid UTF-8") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    values: dict[str, str] = {}
    allowed = {"PLANE_BASE_URL", "PLANE_API_KEY"}
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line != stripped or "=" not in stripped:
            raise WorkflowError(f"invalid Plane connection entry at {path}:{number}")
        key, value = stripped.split("=", 1)
        if (
            key not in allowed
            or not value
            or value != value.strip()
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
            or key in values
        ):
            raise WorkflowError(f"invalid Plane connection key at {path}:{number}")
        values[key] = value
    if set(values) != allowed:
        raise WorkflowError(
            f"Plane connection file {path} must define PLANE_BASE_URL and PLANE_API_KEY"
        )
    return values


def _load_plane_connection() -> tuple[str, str]:
    base_url = os.environ.get("PLANE_BASE_URL")
    api_key = os.environ.get("PLANE_API_KEY")
    for name, value in (("PLANE_BASE_URL", base_url), ("PLANE_API_KEY", api_key)):
        if value is not None and (
            not value.strip()
            or value != value.strip()
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
        ):
            raise WorkflowError(
                f"{name} must be non-blank without surrounding whitespace or control characters"
            )
    if not base_url or not api_key:
        connection_path = Path(
            os.environ.get("PLANE_CONNECTION_FILE", PLANE_CONNECTION_FILE)
        ).expanduser()
        if os.path.lexists(connection_path):
            file_env = _read_plane_connection_file(connection_path)
            base_url = base_url or file_env.get("PLANE_BASE_URL")
            api_key = api_key or file_env.get("PLANE_API_KEY")
        elif "PLANE_CONNECTION_FILE" in os.environ:
            raise WorkflowError(f"Plane connection file does not exist: {connection_path}")
    if not base_url or not api_key:
        raise WorkflowError(
            "Plane connection is missing; configure both PLANE_BASE_URL and PLANE_API_KEY in "
            f"{PLANE_CONNECTION_FILE} (mode 600) or the process environment"
        )
    return str(base_url), str(api_key)


class PlaneClient:
    def __init__(self, base_url: str, api_key: str, workspace: str, project_id: str) -> None:
        base = base_url.rstrip("/")
        self.base_url = base if base.endswith("/api/v1") else base + "/api/v1"
        self.api_key = api_key
        self.workspace = workspace
        self.project_id = project_id
        self.transport_events: list[str] = []

    @classmethod
    def from_route(cls, route: dict[str, Any]) -> "PlaneClient":
        base_url, api_key = _load_plane_connection()
        return cls(base_url, api_key, route["workspace"], route["project_id"])

    def _path(self, suffix: str) -> str:
        workspace = urllib.parse.quote(self.workspace, safe="")
        return f"workspaces/{workspace}/{suffix.strip('/')}"

    @staticmethod
    def _transport_reason(error: BaseException) -> BaseException | str:
        if isinstance(error, urllib.error.URLError):
            return error.reason
        return error

    def _redact_api_key(self, value: object) -> str:
        rendered = str(value)
        return rendered.replace(self.api_key, "<redacted>") if self.api_key else rendered

    @classmethod
    def _is_retryable_read_error(cls, error: BaseException) -> bool:
        reason = cls._transport_reason(error)
        return isinstance(
            reason,
            (
                ssl.SSLEOFError,
                ConnectionResetError,
                ConnectionAbortedError,
                TimeoutError,
                http.client.RemoteDisconnected,
            ),
        )

    @classmethod
    def _is_proxy_tunnel_auth_error(cls, error: BaseException) -> bool:
        if not isinstance(error, urllib.error.URLError) or isinstance(error, urllib.error.HTTPError):
            return False
        return PROXY_TUNNEL_407_RE.fullmatch(str(cls._transport_reason(error))) is not None

    def _open_payload(
        self,
        method: str,
        suffix: str,
        make_request: Any,
        open_request: Any,
        *,
        transport: str,
    ) -> bytes:
        attempts = SAFE_READ_ATTEMPTS if method.upper() == "GET" else 1
        for attempt in range(1, attempts + 1):
            try:
                with open_request(make_request(), timeout=30) as response:
                    return response.read()
            except urllib.error.HTTPError:
                raise
            except (
                urllib.error.URLError,
                ssl.SSLEOFError,
                ConnectionResetError,
                ConnectionAbortedError,
                TimeoutError,
                http.client.RemoteDisconnected,
            ) as error:
                if method.upper() != "GET" or not self._is_retryable_read_error(error):
                    raise
                if attempt == attempts:
                    raise SafeReadRetryExhausted(attempts, error) from error
                self.transport_events.append(
                    f"transient GET transport error on {transport} request; "
                    f"retry {attempt + 1}/{attempts} for {suffix}"
                )
        raise AssertionError("safe read retry loop exited unexpectedly")

    def _open_direct_payload(self, method: str, suffix: str, make_request: Any) -> bytes:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            return self._open_payload(
                method,
                suffix,
                make_request,
                opener.open,
                transport="direct",
            )
        except urllib.error.HTTPError as error:
            detail = self._redact_api_key(
                error.read().decode("utf-8", errors="replace")[:2000]
            )
            raise WorkflowError(
                f"Plane direct retry for {method} {suffix} failed: HTTP {error.code}: {detail}"
            ) from error
        except SafeReadRetryExhausted as error:
            reason = self._redact_api_key(self._transport_reason(error.cause))
            raise WorkflowError(
                f"Plane direct retry for {method} {suffix} failed after "
                f"{error.attempts} safe-read attempts: {reason}"
            ) from error
        except (
            urllib.error.URLError,
            ssl.SSLEOFError,
            ConnectionResetError,
            ConnectionAbortedError,
            TimeoutError,
            http.client.RemoteDisconnected,
        ) as error:
            raise WorkflowError(
                f"Plane direct retry for {method} {suffix} failed: "
                f"{self._redact_api_key(self._transport_reason(error))}"
            ) from error

    def request(
        self,
        method: str,
        suffix: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{self._path(suffix)}/"
        if params:
            query = urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})
            url += "?" + query
        body = json.dumps(data).encode("utf-8") if data is not None else None
        def make_request() -> urllib.request.Request:
            return urllib.request.Request(
                url,
                data=body,
                method=method,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "plane-workflow/1.0",
                    "X-Api-Key": self.api_key,
                },
            )

        try:
            payload = self._open_payload(
                method,
                suffix,
                make_request,
                urllib.request.urlopen,
                transport="configured",
            )
        except urllib.error.HTTPError as error:
            if error.code == 407 and os.environ.get("PLANE_REQUIRE_PROXY") != "1":
                self.transport_events.append("proxy returned HTTP 407; retried this Plane host directly")
                payload = self._open_direct_payload(method, suffix, make_request)
            else:
                detail = self._redact_api_key(
                    error.read().decode("utf-8", errors="replace")[:2000]
                )
                raise WorkflowError(f"Plane {method} {suffix} failed: HTTP {error.code}: {detail}") from error
        except SafeReadRetryExhausted as error:
            reason = self._redact_api_key(self._transport_reason(error.cause))
            raise WorkflowError(
                f"Plane {method} {suffix} failed after {error.attempts} safe-read attempts: {reason}"
            ) from error
        except (
            urllib.error.URLError,
            ssl.SSLEOFError,
            ConnectionResetError,
            ConnectionAbortedError,
            TimeoutError,
            http.client.RemoteDisconnected,
        ) as error:
            reason = self._redact_api_key(self._transport_reason(error))
            if self._is_proxy_tunnel_auth_error(error) and os.environ.get("PLANE_REQUIRE_PROXY") != "1":
                self.transport_events.append("proxy returned HTTP 407; retried this Plane host directly")
                payload = self._open_direct_payload(method, suffix, make_request)
            else:
                raise WorkflowError(f"Plane {method} {suffix} failed: {reason}") from error
        if not payload:
            return None
        return json.loads(payload)

    @property
    def project_prefix(self) -> str:
        return f"projects/{self.project_id}"

    def project(self) -> dict[str, Any]:
        return self.request("GET", self.project_prefix)

    def list_all(self, suffix: str, **params: Any) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            query = {"per_page": 100, **params, "cursor": cursor}
            payload = self.request("GET", suffix, params=query)
            if isinstance(payload, list):
                results.extend(payload)
                break
            if not isinstance(payload, dict):
                raise WorkflowError(f"unexpected list response from {suffix}")
            page = payload.get("results", payload.get("issues", []))
            if not isinstance(page, list):
                raise WorkflowError(f"unexpected result envelope from {suffix}")
            results.extend(page)
            cursor = payload.get("next_cursor")
            if not cursor or not payload.get("next_page_results", bool(cursor)):
                break
        return results

    def states(self) -> list[dict[str, Any]]:
        return self.list_all(f"{self.project_prefix}/states")

    def labels(self) -> list[dict[str, Any]]:
        return self.list_all(f"{self.project_prefix}/labels")

    def modules(self) -> list[dict[str, Any]]:
        return self.list_all(f"{self.project_prefix}/modules")

    def work_items(self) -> list[dict[str, Any]]:
        return self.list_all(f"{self.project_prefix}/work-items", expand="state,labels")

    def retrieve_work_item(self, item_id: str) -> dict[str, Any]:
        return self.request("GET", f"{self.project_prefix}/work-items/{item_id}")

    def retrieve_module(self, module_id: str) -> dict[str, Any]:
        return self.request("GET", f"{self.project_prefix}/modules/{module_id}")

    def module_work_items(self, module_id: str) -> list[dict[str, Any]]:
        return self.list_all(f"{self.project_prefix}/modules/{module_id}/module-issues")


def object_id(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("id")
    return None


def assert_project(route: dict[str, Any], project: dict[str, Any]) -> None:
    mismatches = []
    for route_key, project_key in (("project_id", "id"), ("project_identifier", "identifier"), ("project_name", "name")):
        if str(project.get(project_key)) != route[route_key]:
            mismatches.append(f"{project_key}={project.get(project_key)!r}, expected {route[route_key]!r}")
    if project.get("external_source") not in (None, route["external_source"]):
        mismatches.append(
            f"external_source={project.get('external_source')!r}, expected {route['external_source']!r}"
        )
    if mismatches:
        raise WorkflowError("repository route conflicts with retrieved project: " + "; ".join(mismatches))


def assert_active_project(project: dict[str, Any]) -> None:
    if project.get("archived_at"):
        raise WorkflowError("Plane project is archived; restore and re-list retained hierarchy before writes")


def _match_unique(
    items: Iterable[dict[str, Any]],
    *,
    external_source: str,
    external_id: str,
    name: str,
    parent_id: str | None = None,
) -> dict[str, Any] | None:
    item_list = list(items)
    external = [
        item
        for item in item_list
        if item.get("external_source") == external_source and item.get("external_id") == external_id
    ]
    if len(external) > 1:
        raise WorkflowError(f"ambiguous external ID {external_source}:{external_id}")
    if external:
        return external[0]
    exact = [item for item in item_list if item.get("name") == name]
    if parent_id is not None:
        exact = [item for item in exact if object_id(item.get("parent")) == parent_id]
    if len(exact) > 1:
        raise WorkflowError(f"ambiguous exact name/parent match for {name!r}")
    return exact[0] if exact else None


def resolve_state(states: list[dict[str, Any]], target: str) -> dict[str, Any]:
    if target == "unstarted":
        groups, names = {"backlog", "unstarted"}, {"backlog", "todo", "to do"}
    elif target == "started":
        groups, names = {"started"}, {"in progress", "started"}
    elif target == "review":
        groups, names = set(), {"review", "in review", "under review"}
    elif target == "completed":
        groups, names = {"completed"}, {"done", "completed"}
    elif target == "cancelled":
        groups, names = {"cancelled"}, {"cancelled", "canceled"}
    else:
        raise WorkflowError(f"unknown state target {target}")
    matches = [
        state
        for state in states
        if str(state.get("group", "")).lower() in groups
        or str(state.get("name", "")).lower() in names
    ]
    if not matches:
        raise WorkflowError(f"cannot resolve {target} state in project")
    matches.sort(key=lambda value: (str(value.get("group", "")).lower() not in groups, value.get("sequence", 0)))
    return matches[0]


class _CanonicalHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = []
        for key, value in attrs:
            if key in {"class", "data-id"}:
                continue
            if key in {"checked", "disabled", "selected"}:
                normalized.append((key, ""))
            else:
                normalized.append((key, value or ""))
        attributes = "".join(
            f' {key}="{html.escape(value, quote=True)}"' for key, value in sorted(normalized)
        )
        self.parts.append(f"<{tag}{attributes}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        normalized = " ".join(data.split())
        if normalized:
            self.parts.append(html.escape(normalized))


def _canonical_html(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"^\s*<div[^>]*>(.*)</div>\s*$", r"\1", value, flags=re.DOTALL)
    parser = _CanonicalHTMLParser()
    parser.feed(value)
    return "".join(parser.parts)


def _drift(current: dict[str, Any], desired: dict[str, Any]) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for key, value in desired.items():
        existing = object_id(current.get(key)) if key in {"parent", "state"} else current.get(key)
        if key == "labels":
            existing = sorted(filter(None, (object_id(item) for item in (existing or []))))
            value = sorted(value)
        if key == "description_html":
            if _canonical_html(existing) != _canonical_html(value):
                changed[key] = value
        elif existing != value:
            changed[key] = value
    return changed


@dataclass
class ReconcileResult:
    actions: list[dict[str, Any]]
    objects: dict[str, Any]


def reconcile_work_package(
    client: PlaneClient,
    route: dict[str, Any],
    plan: dict[str, Any],
    *,
    apply: bool,
) -> ReconcileResult:
    project = client.project()
    assert_project(route, project)
    assert_active_project(project)
    rendered = render_objects(plan, route["external_source"])
    states = client.states()
    unstarted = resolve_state(states, "unstarted")
    modules = client.modules()
    labels = client.labels()
    items = client.work_items()
    actions: list[dict[str, Any]] = []

    module_spec = rendered["module"]
    module = _match_unique(
        modules,
        external_source=module_spec["external_source"],
        external_id=module_spec["external_id"],
        name=module_spec["name"],
    )
    module_payload = {key: module_spec[key] for key in ("name", "description", "status", "external_source", "external_id")}
    if module is None:
        actions.append({"action": "create", "kind": "module", "external_id": module_spec["external_id"]})
        if apply:
            module = client.request("POST", f"{client.project_prefix}/modules", data=module_payload)
            module = client.retrieve_module(module["id"])
        else:
            module = {"id": "<new-module>", **module_payload}
    else:
        module_update_payload = dict(module_payload)
        module_update_payload.pop("status", None)
        changed = _drift(module, module_update_payload)
        if changed:
            actions.append({"action": "update", "kind": "module", "id": module["id"], "fields": sorted(changed)})
            if apply:
                client.request("PATCH", f"{client.project_prefix}/modules/{module['id']}", data=changed)
                module = client.retrieve_module(module["id"])

    wp = plan["work_package"]
    label_matches = [item for item in labels if item.get("name") == wp["id"]]
    if len(label_matches) > 1:
        raise WorkflowError(f"ambiguous duplicate label name {wp['id']}")
    label = label_matches[0] if label_matches else None
    desired_label_color = wp.get("label_color", "#0F766E")
    if label is None:
        actions.append({"action": "create", "kind": "label", "name": wp["id"]})
        if apply:
            label = client.request(
                "POST",
                f"{client.project_prefix}/labels",
                data={"name": wp["id"], "color": desired_label_color},
            )
            label = client.request("GET", f"{client.project_prefix}/labels/{label['id']}")
        else:
            label = {"id": "<new-label>", "name": wp["id"], "color": desired_label_color}
    elif str(label.get("color", "")).lower() != str(desired_label_color).lower():
        actions.append({"action": "update", "kind": "label", "id": label["id"], "fields": ["color"]})
        if apply:
            client.request(
                "PATCH",
                f"{client.project_prefix}/labels/{label['id']}",
                data={"color": desired_label_color},
            )
            label = client.request("GET", f"{client.project_prefix}/labels/{label['id']}")

    def reconcile_item(spec: dict[str, Any], parent_id: str | None, with_label: bool) -> dict[str, Any]:
        current = _match_unique(
            items,
            external_source=spec["external_source"],
            external_id=spec["external_id"],
            name=spec["name"],
            parent_id=parent_id,
        )
        payload = {
            key: spec[key]
            for key in ("name", "description_html", "priority", "start_date", "target_date", "external_source", "external_id")
        }
        payload["state"] = unstarted["id"]
        if parent_id:
            payload["parent"] = parent_id
        if with_label:
            existing_labels = [] if current is None else [
                item_id
                for item_id in (object_id(item) for item in (current.get("labels") or []))
                if item_id
            ]
            payload["labels"] = sorted(set(existing_labels) | {label["id"]})
        if current is None:
            actions.append({"action": "create", "kind": "work_item", "external_id": spec["external_id"]})
            if apply:
                current = client.request("POST", f"{client.project_prefix}/work-items", data=payload)
                current = client.retrieve_work_item(current["id"])
                items.append(current)
            else:
                current = {"id": f"<new:{spec['external_id']}>", **payload}
        else:
            update_payload = dict(payload)
            update_payload.pop("state", None)
            changed = _drift(current, update_payload)
            if changed:
                actions.append({"action": "update", "kind": "work_item", "id": current["id"], "fields": sorted(changed)})
                if apply:
                    client.request("PATCH", f"{client.project_prefix}/work-items/{current['id']}", data=changed)
                    current = client.retrieve_work_item(current["id"])
        return current

    requirement = reconcile_item(rendered["requirement"], None, False)
    work_package = reconcile_item(rendered["work_package"], requirement["id"], True)
    phases = [reconcile_item(spec, work_package["id"], True) for spec in rendered["phases"]]
    all_ids = [requirement["id"], work_package["id"], *(phase["id"] for phase in phases)]
    if not str(module["id"]).startswith("<new-"):
        membership = {item["id"] for item in client.module_work_items(module["id"])}
    else:
        membership = set()
    missing_ids = [item_id for item_id in all_ids if item_id not in membership]
    if missing_ids:
        actions.append({"action": "add", "kind": "module_work_items", "count": len(missing_ids)})
        if apply:
            client.request(
                "POST",
                f"{client.project_prefix}/modules/{module['id']}/module-issues",
                data={"issues": missing_ids},
            )
            post_membership = {item["id"] for item in client.module_work_items(module["id"])}
            still_missing = [item_id for item_id in all_ids if item_id not in post_membership]
            if still_missing:
                raise WorkflowError(
                    f"Module membership update was not confirmed; {len(still_missing)} items remain missing"
                )
    resolved = {"module": module, "requirement": requirement, "work_package": work_package, "phases": phases}
    if apply:
        verify_hierarchy(client, route, plan)
    return ReconcileResult(actions=actions, objects=resolved)


def verify_hierarchy(client: PlaneClient, route: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    project = client.project()
    assert_project(route, project)
    rendered = render_objects(plan, route["external_source"])
    modules = client.modules()
    items = client.work_items()
    module_spec = rendered["module"]
    module = _match_unique(
        modules,
        external_source=module_spec["external_source"],
        external_id=module_spec["external_id"],
        name=module_spec["name"],
    )
    if module is None:
        raise WorkflowError(f"missing Module {module_spec['external_id']}")
    module = client.retrieve_module(module["id"])
    module_expected = {
        key: module_spec[key]
        for key in ("name", "description", "external_source", "external_id")
    }
    module_drift = _drift(module, module_expected)
    if module_drift:
        raise WorkflowError("Module verification drift: " + ", ".join(sorted(module_drift)))
    requirement = _match_unique(items, external_source=route["external_source"], external_id=rendered["requirement"]["external_id"], name=rendered["requirement"]["name"])
    if requirement is None:
        raise WorkflowError("missing Requirement work item")
    requirement = client.retrieve_work_item(requirement["id"])
    wp_spec = rendered["work_package"]
    work_package = _match_unique(items, external_source=route["external_source"], external_id=wp_spec["external_id"], name=wp_spec["name"], parent_id=requirement["id"])
    if work_package is None:
        raise WorkflowError("missing Work Package or incorrect Requirement parent")
    work_package = client.retrieve_work_item(work_package["id"])
    phases = []
    for spec in rendered["phases"]:
        phase = _match_unique(items, external_source=route["external_source"], external_id=spec["external_id"], name=spec["name"], parent_id=work_package["id"])
        if phase is None:
            raise WorkflowError(f"missing Phase or incorrect WP parent: {spec['external_id']}")
        phases.append(client.retrieve_work_item(phase["id"]))

    label = next((item for item in client.labels() if item.get("name") == plan["work_package"]["id"]), None)
    if label is None:
        raise WorkflowError(f"missing Work Package label {plan['work_package']['id']}")
    expected_label_color = str(plan["work_package"].get("label_color", "#0F766E"))
    if str(label.get("color", "")).lower() != expected_label_color.lower():
        raise WorkflowError(
            f"label color drift for {label['name']}: {label.get('color')!r}, expected {expected_label_color!r}"
        )

    def assert_item(item: dict[str, Any], spec: dict[str, Any], parent_id: str | None, require_label: bool) -> None:
        expected = {
            key: spec[key]
            for key in (
                "name",
                "description_html",
                "priority",
                "start_date",
                "target_date",
                "external_source",
                "external_id",
            )
        }
        expected["parent"] = parent_id
        drift = _drift(item, expected)
        if drift:
            raise WorkflowError(
                f"work item verification drift for {spec['external_id']}: "
                + ", ".join(sorted(drift))
            )
        if require_label:
            label_ids = {object_id(value) for value in (item.get("labels") or [])}
            if label["id"] not in label_ids:
                raise WorkflowError(f"missing {label['name']} label on {spec['external_id']}")

    assert_item(requirement, rendered["requirement"], None, False)
    assert_item(work_package, wp_spec, requirement["id"], True)
    for phase, spec in zip(phases, rendered["phases"]):
        assert_item(phase, spec, work_package["id"], True)
    membership = {item["id"] for item in client.module_work_items(module["id"])}
    expected = {requirement["id"], work_package["id"], *(phase["id"] for phase in phases)}
    missing = sorted(expected - membership)
    if missing:
        raise WorkflowError(f"Module membership is missing {len(missing)} work items")
    return {
        "verified": True,
        "project_id": project["id"],
        "module_id": module["id"],
        "requirement_id": requirement["id"],
        "work_package_id": work_package["id"],
        "phase_ids": [phase["id"] for phase in phases],
    }


def find_work_package(
    items: list[dict[str, Any]], route: dict[str, Any], wp_id: str
) -> dict[str, Any]:
    work_package = _match_unique(
        items,
        external_source=route["external_source"],
        external_id=f"work-package:{wp_id}",
        name=wp_id,
    )
    if work_package is None:
        raise WorkflowError(f"cannot find work-package:{wp_id}")
    return work_package


def find_phase(client: PlaneClient, route: dict[str, Any], wp_id: str, phase: int) -> dict[str, Any]:
    external_id = f"phase:{wp_id}:{phase}"
    items = client.work_items()
    work_package = find_work_package(items, route, wp_id)
    item = _match_unique(
        items,
        external_source=route["external_source"],
        external_id=external_id,
        name=f"Phase {phase}",
    )
    if item is None:
        raise WorkflowError(f"cannot find {external_id}")
    if object_id(item.get("parent")) != work_package["id"]:
        raise WorkflowError(f"{external_id} is not a direct child of work-package:{wp_id}")
    return client.retrieve_work_item(item["id"])


def phase_has_closure_evidence(item: dict[str, Any], completed_state_id: str) -> bool:
    summary = phase_summary(item.get("description_html") or "")
    return (
        object_id(item.get("state")) == completed_state_id
        and summary["complete"]
        and completion_evidence_valid(summary)
    )


def validate_phase_start_sequence(
    phases: list[dict[str, Any]], target_number: int, completed_state_id: str, started_state_id: str
) -> dict[str, Any]:
    numbered: dict[int, dict[str, Any]] = {}
    for item in phases:
        external_id = str(item.get("external_id", ""))
        try:
            number = int(external_id.rsplit(":", 1)[1])
        except (ValueError, IndexError):
            raise WorkflowError(f"invalid Phase external ID: {external_id!r}")
        if number in numbered:
            raise WorkflowError(f"duplicate Phase number {number}")
        numbered[number] = item
    target = numbered.get(target_number)
    if target is None:
        raise WorkflowError(f"Phase {target_number} is not present")
    missing = [number for number in range(target_number) if number not in numbered]
    if missing:
        raise WorkflowError("Phase sequence is missing earlier numbers: " + ", ".join(map(str, missing)))
    unclosed = [
        number
        for number in range(target_number)
        if not phase_has_closure_evidence(numbered[number], completed_state_id)
    ]
    if unclosed:
        raise WorkflowError(
            "cannot start Phase before earlier Phases are semantically complete: "
            + ", ".join(map(str, unclosed))
        )
    other_started = [
        number
        for number, item in numbered.items()
        if number != target_number and object_id(item.get("state")) == started_state_id
    ]
    if other_started:
        raise WorkflowError("another Phase is already In Progress: " + ", ".join(map(str, other_started)))
    if object_id(target.get("state")) == completed_state_id:
        raise WorkflowError(f"Phase {target_number} is already Done")
    return target


def inspect_project(client: PlaneClient, route: dict[str, Any]) -> dict[str, Any]:
    project = client.project()
    assert_project(route, project)
    return {
        "verified": True,
        "route": route,
        "project": {key: project.get(key) for key in ("id", "identifier", "name", "archived_at", "external_source", "external_id")},
        "states": [{key: state.get(key) for key in ("id", "name", "group")} for state in client.states()],
        "labels": [{key: label.get(key) for key in ("id", "name", "color")} for label in client.labels()],
        "modules": [{key: module.get(key) for key in ("id", "name", "status", "external_id")} for module in client.modules()],
        "transport_events": list(dict.fromkeys(client.transport_events)),
    }


def inspect_wp(client: PlaneClient, route: dict[str, Any], wp_id: str) -> dict[str, Any]:
    project = client.project()
    assert_project(route, project)
    items = client.work_items()
    wp = _match_unique(items, external_source=route["external_source"], external_id=f"work-package:{wp_id}", name=wp_id)
    if wp is None:
        raise WorkflowError(f"cannot find work-package:{wp_id}")
    phase_candidates = [
        item
        for item in items
        if item.get("external_source") == route["external_source"]
        and str(item.get("external_id", "")).startswith(f"phase:{wp_id}:")
    ]
    detached = [item.get("external_id") for item in phase_candidates if object_id(item.get("parent")) != wp["id"]]
    if detached:
        raise WorkflowError(
            "Phase hierarchy drift; these items are not direct WP children: "
            + ", ".join(map(str, detached))
        )
    phases = [
        client.retrieve_work_item(item["id"])
        for item in phase_candidates
    ]
    phases.sort(key=lambda item: int(str(item["external_id"]).rsplit(":", 1)[1]))
    return {
        "verified_project": True,
        "work_package": {key: wp.get(key) for key in ("id", "name", "external_id", "state", "start_date", "target_date")},
        "phases": [
            {
                "id": item["id"],
                "name": item["name"],
                "external_id": item.get("external_id"),
                "state": item.get("state"),
                "summary": phase_summary(item.get("description_html") or ""),
            }
            for item in phases
        ],
    }


def delete_unstarted_work_package(
    client: PlaneClient,
    route: dict[str, Any],
    plan: dict[str, Any],
    *,
    apply: bool,
) -> dict[str, Any]:
    """Delete a never-started Requirement hierarchy while preserving its Module."""

    errors = validate_plan(plan)
    if errors:
        raise WorkflowError("invalid plan: " + "; ".join(errors))

    project = client.project()
    assert_project(route, project)
    assert_active_project(project)
    wp_id = plan["work_package"]["id"]
    requirement_external_id = f"requirement:{plan['requirement']['id']}"
    module_external_id = f"module:{plan['module']['id']}"
    work_package_external_id = f"work-package:{wp_id}"
    states = client.states()
    deletable_state_ids = {
        state["id"]
        for state in states
        if state.get("group") in {"backlog", "unstarted"}
    }
    if not deletable_state_ids:
        raise WorkflowError("Plane project has no Backlog or unstarted state")

    items = client.work_items()
    requirement = _match_unique(
        items,
        external_source=route["external_source"],
        external_id=requirement_external_id,
        name=plan["requirement"]["id"],
    )
    work_package = _match_unique(
        items,
        external_source=route["external_source"],
        external_id=work_package_external_id,
        name=wp_id,
    )
    phase_candidates = [
        item
        for item in items
        if item.get("external_source") == route["external_source"]
        and str(item.get("external_id", "")).startswith(f"phase:{wp_id}:")
    ]

    modules = [
        module
        for module in client.modules()
        if module.get("external_source") == route["external_source"]
        and module.get("external_id") == module_external_id
    ]
    if len(modules) != 1:
        raise WorkflowError(f"expected exactly one preserved {module_external_id} Module")
    module = client.retrieve_module(modules[0]["id"])

    if requirement is None and work_package is None and not phase_candidates:
        return {
            "actions": [],
            "already_absent": True,
            "applied": apply,
            "module": module_external_id,
            "verified": True,
            "work_package": work_package_external_id,
        }
    if requirement is None:
        raise WorkflowError("cannot safely delete a Work Package hierarchy without its Requirement")
    requirement = client.retrieve_work_item(requirement["id"])
    if work_package is not None:
        work_package = client.retrieve_work_item(work_package["id"])
        if object_id(work_package.get("parent")) != requirement["id"]:
            raise WorkflowError("Work Package is not a direct child of the expected Requirement")

    requirement_children = [
        item for item in items if object_id(item.get("parent")) == requirement["id"]
    ]
    allowed_requirement_children = {work_package["id"]} if work_package is not None else set()
    unexpected_requirement_children = [
        item.get("external_id") or item["id"]
        for item in requirement_children
        if item["id"] not in allowed_requirement_children
    ]
    if unexpected_requirement_children:
        raise WorkflowError(
            "Requirement has unrelated direct children: "
            + ", ".join(map(str, unexpected_requirement_children))
        )

    if phase_candidates and work_package is None:
        raise WorkflowError("orphan Phase items remain after the Work Package disappeared")
    detached_phases = [
        item.get("external_id") or item["id"]
        for item in phase_candidates
        if work_package is None or object_id(item.get("parent")) != work_package["id"]
    ]
    if detached_phases:
        raise WorkflowError(
            "Phase hierarchy drift prevents deletion: " + ", ".join(map(str, detached_phases))
        )
    if work_package is not None:
        direct_children = [
            item for item in items if object_id(item.get("parent")) == work_package["id"]
        ]
        phase_ids = {item["id"] for item in phase_candidates}
        unexpected_wp_children = [
            item.get("external_id") or item["id"]
            for item in direct_children
            if item["id"] not in phase_ids
        ]
        if unexpected_wp_children:
            raise WorkflowError(
                "Work Package has non-Phase direct children: "
                + ", ".join(map(str, unexpected_wp_children))
            )
    descendant_ids = {item["id"] for item in phase_candidates}
    nested_descendants = [
        item.get("external_id") or item["id"]
        for item in items
        if object_id(item.get("parent")) in descendant_ids
    ]
    if nested_descendants:
        raise WorkflowError(
            "Phase descendants prevent deletion: " + ", ".join(map(str, nested_descendants))
        )

    present_items = [requirement]
    if work_package is not None:
        present_items.append(work_package)
    phases = [client.retrieve_work_item(item["id"]) for item in phase_candidates]
    phases.sort(key=lambda item: int(str(item["external_id"]).rsplit(":", 1)[1]))
    present_items.extend(phases)
    wrong_states = [
        item.get("external_id") or item["id"]
        for item in present_items
        if object_id(item.get("state")) not in deletable_state_ids
    ]
    if wrong_states:
        raise WorkflowError(
            "delete-unstarted refuses started, completed, or cancelled items: "
            + ", ".join(map(str, wrong_states))
        )
    evidenced_phases = []
    for phase in phases:
        summary = phase_summary(phase.get("description_html") or "")
        if summary["checked"] != 0 or summary["complete"] or "实际证据" in summary["sections"]:
            evidenced_phases.append(phase.get("external_id") or phase["id"])
    if evidenced_phases:
        raise WorkflowError(
            "delete-unstarted refuses Phase checklist or actual evidence: "
            + ", ".join(map(str, evidenced_phases))
        )

    memberships = []
    containing_modules = []
    hierarchy_ids = {item["id"] for item in present_items}
    for candidate in client.modules():
        membership = client.module_work_items(candidate["id"])
        memberships.append((candidate, membership))
        member_ids = {item["id"] for item in membership}
        if hierarchy_ids.intersection(member_ids):
            containing_modules.append((candidate, member_ids))
    if len(containing_modules) != 1 or containing_modules[0][0]["id"] != module["id"]:
        raise WorkflowError("unstarted hierarchy must belong only to its exact preserved Module")
    if not hierarchy_ids.issubset(containing_modules[0][1]):
        raise WorkflowError("preserved Module membership omits part of the unstarted hierarchy")
    conflicting_modules = [
        candidate.get("external_id") or candidate["id"]
        for candidate, membership in memberships
        if candidate["id"] != module["id"]
        and hierarchy_ids.intersection({item["id"] for item in membership})
    ]
    if conflicting_modules:
        raise WorkflowError(
            "unstarted hierarchy belongs to more than one Module: "
            + ", ".join(map(str, conflicting_modules))
        )
    validate_closure_module_identity(route, requirement, module)

    ordered = [*reversed(phases)]
    if work_package is not None:
        ordered.append(work_package)
    ordered.append(requirement)
    actions = [
        {
            "kind": (
                "phase"
                if str(item.get("external_id", "")).startswith("phase:")
                else "work_package"
                if item.get("external_id") == work_package_external_id
                else "requirement"
            ),
            "id": item["id"],
            "external_id": item.get("external_id"),
        }
        for item in ordered
    ]

    if apply:
        for item in ordered:
            client.request("DELETE", f"{client.project_prefix}/work-items/{item['id']}")
            remaining_ids = {candidate["id"] for candidate in client.work_items()}
            if item["id"] in remaining_ids:
                raise WorkflowError(
                    f"DELETE was not confirmed by re-read: {item.get('external_id') or item['id']}"
                )
        reread_module = client.retrieve_module(module["id"])
        if (
            reread_module.get("external_id") != module_external_id
            or reread_module.get("status") != module.get("status")
        ):
            raise WorkflowError("preserved Module changed during unstarted hierarchy deletion")
        remaining_members = {
            item["id"] for item in client.module_work_items(module["id"])
        }
        if hierarchy_ids.intersection(remaining_members):
            raise WorkflowError("deleted hierarchy still appears in preserved Module membership")

    return {
        "actions": actions,
        "already_absent": False,
        "applied": apply,
        "module": module_external_id,
        "verified": apply,
        "work_package": work_package_external_id,
    }


def validate_closure_module_identity(
    route: dict[str, Any], requirement: dict[str, Any], module: dict[str, Any]
) -> None:
    requirement_external_id = str(requirement.get("external_id", ""))
    if (
        requirement.get("external_source") != route["external_source"]
        or not requirement_external_id.startswith("requirement:")
    ):
        raise WorkflowError("Requirement parent lacks the repository's stable external identity")
    expected_module_id = "module:" + requirement_external_id.removeprefix("requirement:")
    if (
        module.get("external_source") != route["external_source"]
        or module.get("external_id") != expected_module_id
    ):
        raise WorkflowError(
            f"Work Package belongs to an unrelated Module; expected {expected_module_id}"
        )


def current_git_revision(repository: str) -> str:
    completed = subprocess.run(
        ["git", "-C", repository, "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    revision = completed.stdout.strip().lower()
    if completed.returncode != 0 or not GIT_REVISION_RE.fullmatch(revision):
        raise WorkflowError(f"cannot resolve the current Git revision for {repository}")
    return revision


def git_common_directory(repository: str) -> str:
    completed = subprocess.run(
        ["git", "-C", repository, "rev-parse", "--git-common-dir"],
        text=True,
        capture_output=True,
        check=False,
    )
    common_directory = completed.stdout.strip()
    if completed.returncode != 0 or not common_directory:
        raise WorkflowError(f"cannot resolve the Git common directory for {repository}")
    path = Path(common_directory)
    if not path.is_absolute():
        path = Path(repository) / path
    return str(path.resolve())


def git_paths_share_common_directory(first: str, second: str) -> bool:
    return first == second or git_common_directory(first) == git_common_directory(second)


def git_commit_chain(
    repository: str, base_revision: str, head_revision: str
) -> list[tuple[str, str]]:
    completed = subprocess.run(
        [
            "git",
            "-C",
            repository,
            "rev-list",
            "--reverse",
            "--topo-order",
            f"{base_revision}..{head_revision}",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    commits = [line.strip().lower() for line in completed.stdout.splitlines() if line.strip()]
    if (
        completed.returncode != 0
        or not commits
        or any(not GIT_REVISION_RE.fullmatch(item) for item in commits)
    ):
        raise WorkflowError(
            f"cannot resolve a non-empty Git commit chain for {repository}"
        )
    chain: list[tuple[str, str]] = []
    expected_parent = base_revision
    for commit_revision in commits:
        parent = subprocess.run(
            ["git", "-C", repository, "rev-list", "--parents", "-n", "1", commit_revision],
            text=True,
            capture_output=True,
            check=False,
        )
        tokens = parent.stdout.strip().lower().split()
        if parent.returncode != 0 or len(tokens) != 2 or tokens[0] != commit_revision:
            raise WorkflowError(
                f"Work Package commit chain for {repository} must be linear and contain no merge commits"
            )
        parent_revision = tokens[1]
        if parent_revision != expected_parent:
            raise WorkflowError(
                f"Work Package commit chain for {repository} is not contiguous"
            )
        chain.append((parent_revision, commit_revision))
        expected_parent = commit_revision
    if expected_parent != head_revision:
        raise WorkflowError(
            f"Work Package commit chain for {repository} does not end at its declared head"
        )
    return chain


def git_commit_parent(repository: str, commit_revision: str) -> str:
    completed = subprocess.run(
        ["git", "-C", repository, "rev-list", "--parents", "-n", "1", commit_revision],
        text=True,
        capture_output=True,
        check=False,
    )
    tokens = completed.stdout.strip().lower().split()
    if completed.returncode != 0 or len(tokens) != 2 or tokens[0] != commit_revision:
        raise WorkflowError(
            f"commit {commit_revision} in {repository} must exist and have exactly one parent"
        )
    return tokens[1]


def git_commit_subject(repository: str, commit_revision: str) -> str:
    completed = subprocess.run(
        ["git", "-C", repository, "show", "-s", "--format=%s", commit_revision],
        text=True,
        capture_output=True,
        check=False,
    )
    subject = completed.stdout.strip()
    if completed.returncode != 0 or not subject:
        raise WorkflowError(f"cannot resolve commit subject for {commit_revision}")
    return subject


def git_tree_revision(repository: str, commit_revision: str) -> str:
    completed = subprocess.run(
        ["git", "-C", repository, "rev-parse", f"{commit_revision}^{{tree}}"],
        text=True,
        capture_output=True,
        check=False,
    )
    revision = completed.stdout.strip().lower()
    if completed.returncode != 0 or not GIT_REVISION_RE.fullmatch(revision):
        raise WorkflowError(f"cannot resolve tree for {commit_revision}")
    return revision


def git_repository_slug(repository: str) -> str:
    completed = subprocess.run(
        ["git", "-C", repository, "remote", "get-url", "origin"],
        text=True,
        capture_output=True,
        check=False,
    )
    remote = completed.stdout.strip()
    if completed.returncode != 0 or not remote:
        raise WorkflowError(f"cannot resolve origin repository identity for {repository}")
    if re.match(r"^[^/@\s]+@[^/:\s]+:", remote):
        path = remote.split(":", 1)[1]
    else:
        parsed = urllib.parse.urlparse(remote)
        if parsed.scheme not in {"http", "https", "ssh"} or not parsed.hostname:
            raise WorkflowError(f"origin for {repository} is not a forge repository URL")
        path = parsed.path
    slug = path.strip("/").removesuffix(".git")
    if not REPOSITORY_SLUG_RE.fullmatch(slug):
        raise WorkflowError(f"cannot derive a canonical repository slug for {repository}")
    return slug


def git_revision_is_ancestor(
    repository: str, ancestor_revision: str, descendant_revision: str
) -> bool:
    completed = subprocess.run(
        [
            "git",
            "-C",
            repository,
            "merge-base",
            "--is-ancestor",
            ancestor_revision,
            descendant_revision,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode not in {0, 1}:
        raise WorkflowError(
            f"cannot verify Git ancestry in {repository}: {ancestor_revision}..{descendant_revision}"
        )
    return completed.returncode == 0


def work_package_and_phases(
    client: PlaneClient,
    route: dict[str, Any],
    wp_id: str,
    *,
    items: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    all_items = items if items is not None else client.work_items()
    work_package = find_work_package(all_items, route, wp_id)
    phase_candidates = [
        item
        for item in all_items
        if item.get("external_source") == route["external_source"]
        and str(item.get("external_id", "")).startswith(f"phase:{wp_id}:")
    ]
    detached = [
        item.get("external_id")
        for item in phase_candidates
        if object_id(item.get("parent")) != work_package["id"]
    ]
    if detached:
        raise WorkflowError(
            "Phase hierarchy drift; these items are not direct WP children: "
            + ", ".join(map(str, detached))
        )
    phases = [client.retrieve_work_item(item["id"]) for item in phase_candidates]
    if not phases:
        raise WorkflowError(f"work-package:{wp_id} has no direct Phase children")
    phases.sort(key=lambda item: int(str(item["external_id"]).rsplit(":", 1)[1]))
    return work_package, phases, all_items


DESIGN_PHASE_HEADINGS = {"目标", "具体任务", "验收标准", "证据", "明确边界"}
DESIGN_WP_HEADINGS = {"目标", "参与仓库", "设计边界", "交付范围", "总体验收"}


def _html_section_blocks(value: str) -> list[tuple[str, str]]:
    canonical = re.sub(r"</?div(?: [^>]*)?>", "", _canonical_html(value))
    first_heading = canonical.find("<h3>")
    if first_heading < 0:
        raise WorkflowError("design reconciliation requires semantic h3 sections")
    prefix = canonical[:first_heading]
    if re.sub(r"</?div(?: [^>]*)?>", "", prefix).strip():
        raise WorkflowError("design reconciliation found content before the first semantic section")
    canonical = canonical[first_heading:]
    blocks = re.split(r"(?=<h3>)", canonical)
    result: list[tuple[str, str]] = []
    for block in blocks:
        if not block:
            continue
        heading = re.match(r"<h3>([^<]+)</h3>", block)
        if heading is None:
            raise WorkflowError("design reconciliation requires semantic h3 sections")
        result.append((html.unescape(heading.group(1)), block))
    return result


def _merge_design_sections(desired: str, current: str, design_headings: set[str]) -> str:
    retained = "".join(
        block for heading, block in _html_section_blocks(current) if heading not in design_headings
    )
    return _canonical_html(desired) + retained


def _replace_phase_boundaries(current: str, desired: str) -> str:
    desired_boundaries = [
        block for heading, block in _html_section_blocks(desired) if heading == "明确边界"
    ]
    if len(desired_boundaries) > 1:
        raise WorkflowError("design reconciliation found duplicate desired Phase boundaries")
    blocks = [
        (heading, block)
        for heading, block in _html_section_blocks(current)
        if heading != "明确边界"
    ]
    output: list[str] = []
    inserted = False
    for heading, block in blocks:
        output.append(block)
        if heading == "证据" and desired_boundaries:
            output.extend(desired_boundaries)
            inserted = True
    if desired_boundaries and not inserted:
        raise WorkflowError("active Phase lacks the evidence section required for boundary placement")
    return "".join(output)


def _workflow_markers(value: str) -> set[str]:
    return set(
        re.findall(
            r"plane-workflow:(?:commit-review|reviewer-session|history-rewrite|wp-mr|wp-merge):v1:[^<\s]+",
            value,
        )
    )


def _item_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    snapshot = {
        key: item.get(key)
        for key in (
            "name", "priority", "start_date", "target_date", "external_source", "external_id",
        )
    }
    snapshot["state"] = object_id(item.get("state"))
    snapshot["parent"] = object_id(item.get("parent"))
    snapshot["labels"] = sorted(
        filter(None, (object_id(value) for value in (item.get("labels") or [])))
    )
    return snapshot


def _phase_contract_matches(current_html: str, desired_html: str) -> bool:
    current, desired = phase_summary(current_html), phase_summary(desired_html)
    return (
        current["tasks"] == desired["tasks"]
        and current["sections"].get("目标") == desired["sections"].get("目标")
        and current["sections"].get("验收标准") == desired["sections"].get("验收标准")
    )


def reconcile_work_package_design(
    client: PlaneClient,
    route: dict[str, Any],
    plan: dict[str, Any],
    *,
    apply: bool,
) -> dict[str, Any]:
    """Reconcile WP design text without changing hierarchy, state, or recorded evidence."""
    errors = validate_plan(plan)
    if errors:
        raise WorkflowError("invalid plan: " + "; ".join(errors))
    project = client.project()
    assert_project(route, project)
    assert_active_project(project)
    rendered = render_objects(plan, route["external_source"])
    work_package, phases, _ = work_package_and_phases(
        client, route, plan["work_package"]["id"]
    )
    work_package = client.retrieve_work_item(work_package["id"])
    desired_phases = {item["external_id"]: item for item in rendered["phases"]}
    existing_phase_ids = [item.get("external_id") for item in phases]
    if (
        len(existing_phase_ids) != len(set(existing_phase_ids))
        or set(existing_phase_ids) != set(desired_phases)
    ):
        raise WorkflowError("design reconciliation requires the exact existing Phase set")
    if work_package_repositories(work_package.get("description_html") or "") != set(
        plan["work_package"]["repositories"]
    ):
        raise WorkflowError("design reconciliation refuses to change participating repositories")

    states = {state["id"]: state for state in client.states()}

    def state_kind(item: dict[str, Any]) -> tuple[str, str]:
        state = states.get(object_id(item.get("state")))
        if state is None:
            raise WorkflowError("design reconciliation cannot resolve an item state")
        return str(state.get("group", "")).lower(), str(state.get("name", "")).lower()

    wp_group, wp_name = state_kind(work_package)
    if wp_group in {"completed", "cancelled"} or wp_name in {"review", "acceptance"}:
        raise WorkflowError("design reconciliation refuses a terminal or review Work Package")

    mutations: list[tuple[dict[str, Any], str]] = []
    desired_wp = rendered["work_package"]["description_html"]
    final_wp = _merge_design_sections(
        desired_wp, str(work_package.get("description_html") or ""), DESIGN_WP_HEADINGS
    )
    if _canonical_html(work_package.get("description_html")) != final_wp:
        mutations.append((work_package, final_wp))

    for phase in phases:
        external_id = str(phase.get("external_id"))
        desired_html = desired_phases[external_id]["description_html"]
        current_html = str(phase.get("description_html") or "")
        group, name = state_kind(phase)
        if group in {"completed", "cancelled"} or name in {"review", "acceptance"}:
            desired_boundaries = phase_summary(desired_html)["sections"].get("明确边界", "")
            current_boundaries = phase_summary(current_html)["sections"].get("明确边界", "")
            if not _phase_contract_matches(current_html, desired_html) or desired_boundaries != current_boundaries:
                raise WorkflowError("design reconciliation refuses to change a terminal or review Phase")
            continue
        if group == "started":
            if not _phase_contract_matches(current_html, desired_html):
                raise WorkflowError("design reconciliation refuses to change an active Phase contract")
            final_html = _replace_phase_boundaries(current_html, desired_html)
            missing = _workflow_markers(current_html) - _workflow_markers(final_html)
            if missing:
                raise WorkflowError("design reconciliation would remove recorded Phase evidence")
            current_summary, final_summary = phase_summary(current_html), phase_summary(final_html)
            if (
                final_summary["checked"] != current_summary["checked"]
                or final_summary["partial_marker_indexes"] != current_summary["partial_marker_indexes"]
                or final_summary["sections"].get("证据") != current_summary["sections"].get("证据")
                or final_summary["sections"].get("实际证据") != current_summary["sections"].get("实际证据")
            ):
                raise WorkflowError("design reconciliation would change active Phase progress or evidence")
        elif group in {"backlog", "unstarted"}:
            summary = phase_summary(current_html)
            retained = [
                heading for heading, _ in _html_section_blocks(current_html)
                if heading not in DESIGN_PHASE_HEADINGS
            ]
            if summary["checked"] or summary["partial_marker_indexes"] or _workflow_markers(current_html) or retained:
                raise WorkflowError("design reconciliation refuses evidenced or progressed unstarted Phase")
            final_html = _canonical_html(desired_html)
        else:
            raise WorkflowError(f"design reconciliation does not support Phase state {name or group!r}")
        if _canonical_html(current_html) != final_html:
            mutations.append((phase, final_html))

    actions = [
        {
            "action": "update", "kind": "work_item", "id": item["id"],
            "external_id": item.get("external_id"), "fields": ["description_html"],
            "preserved_markers": len(_workflow_markers(str(item.get("description_html") or ""))),
        }
        for item, _ in mutations
    ]
    if apply:
        for item, final_html in mutations:
            before = _item_snapshot(item)
            markers = _workflow_markers(str(item.get("description_html") or ""))
            client.request(
                "PATCH", f"{client.project_prefix}/work-items/{item['id']}",
                data={"description_html": final_html},
            )
            reread = client.retrieve_work_item(item["id"])
            if _canonical_html(reread.get("description_html")) != final_html:
                raise WorkflowError("design reconciliation description PATCH was not confirmed by re-read")
            if _item_snapshot(reread) != before or not markers.issubset(
                _workflow_markers(str(reread.get("description_html") or ""))
            ):
                raise WorkflowError("design reconciliation changed protected state or evidence")
    return {
        "actions": actions, "applied": apply, "verified": not actions or apply,
        "work_package": f"work-package:{plan['work_package']['id']}",
    }


def assert_phases_ready_for_wp_review(
    phases: list[dict[str, Any]], completed_state_id: str
) -> None:
    unfinished = [
        item.get("external_id") or item.get("name")
        for item in phases
        if not phase_has_closure_evidence(item, completed_state_id)
    ]
    if unfinished:
        raise WorkflowError(
            "cannot create Work Package MRs; Phases lack Done state, checked tasks, or actual evidence: "
            + ", ".join(map(str, unfinished))
        )


def merge_request_repository(url: str) -> str | None:
    path = urllib.parse.urlparse(url).path.strip("/")
    marker = "/-/merge_requests/"
    if marker in f"/{path}":
        repository = f"/{path}".split(marker, 1)[0].strip("/")
        return repository or None
    return None


def validate_delegate_commands(
    commands: Any, *, base_revision: str, head_revision: str, repository: str
) -> list[str]:
    if not isinstance(commands, list) or not all(isinstance(item, str) for item in commands):
        raise WorkflowError(f"review receipt {repository} commands must be a list of strings")
    preview_commands = []
    rule_commands = []
    for item in commands:
        try:
            tokens = shlex.split(item)
        except ValueError as error:
            raise WorkflowError(
                f"review receipt {repository} contains an invalid command: {error}"
            ) from error
        if tokens[:3] == ["ocr", "delegate", "preview"]:
            preview_commands.append(tokens)
        if tokens[:3] == ["ocr", "delegate", "rule"]:
            rule_commands.append(tokens)
    if len(preview_commands) != 1:
        raise WorkflowError(
            f"review receipt {repository} must include exactly one ocr delegate preview command"
        )
    preview = preview_commands[0]
    for flag, expected_revision in (
        ("--from", base_revision),
        ("--to", head_revision),
    ):
        positions = [index for index, token in enumerate(preview) if token == flag]
        if len(positions) != 1 or positions[0] + 1 >= len(preview):
            raise WorkflowError(
                f"review receipt {repository} preview command must include one {flag} full SHA"
            )
        if preview[positions[0] + 1].lower() != expected_revision:
            raise WorkflowError(
                f"review receipt {repository} preview command {flag} must match its commit revision"
            )
    if "--commit" in preview:
        raise WorkflowError(
            f"review receipt {repository} must use the exact parent-to-commit --from/--to range"
        )
    if "--background" not in preview:
        raise WorkflowError(
            f"review receipt {repository} preview command must include review background"
        )
    if not rule_commands:
        raise WorkflowError(
            f"review receipt {repository} must include ocr delegate rule evidence"
        )
    return commands


def validate_ocr_commands(commands: Any, *, base_revision: str, head_revision: str, repository: str) -> list[str]:
    if not isinstance(commands, list) or not all(isinstance(item, str) for item in commands):
        raise WorkflowError(f"review receipt {repository} commands must be a list of strings")
    review_commands = []
    for item in commands:
        try:
            tokens = shlex.split(item)
        except ValueError as error:
            raise WorkflowError(f"review receipt {repository} contains an invalid command: {error}") from error
        if tokens[:2] == ["ocr", "review"]:
            review_commands.append(tokens)
    if len(review_commands) != 1:
        raise WorkflowError(f"review receipt {repository} must include exactly one ocr review command")
    review = review_commands[0]
    if "--commit" in review:
        pos = review.index("--commit")
        if pos + 1 >= len(review) or review[pos + 1].lower() != head_revision:
            raise WorkflowError(f"review receipt {repository} --commit must match the full commit SHA")
    else:
        for flag, expected in (("--from", base_revision), ("--to", head_revision)):
            positions = [i for i, token in enumerate(review) if token == flag]
            if len(positions) != 1 or positions[0] + 1 >= len(review) or review[positions[0] + 1].lower() != expected:
                raise WorkflowError(f"review receipt {repository} ocr review must include {flag} full SHA")
    if not any(token in {"json", "sarif"} for token in review) or "--format" not in review:
        raise WorkflowError(f"review receipt {repository} ocr review must request JSON or SARIF output")
    if "--output" not in review:
        raise WorkflowError(f"review receipt {repository} ocr review must persist an output file")
    return commands


def _evidence_summary(value: Any, label: str) -> str:
    summary = str(value or "").strip()
    if len(summary) < 24 or any(
        marker in summary.lower() for marker in ("todo", "pending", "待补充", "待回填")
    ):
        raise WorkflowError(f"{label} must contain a real evidence-based conclusion")
    return summary


def _validate_findings(
    findings: Any,
    *,
    repository: str,
    commit_revision: str,
    repository_path: str,
) -> list[dict[str, Any]]:
    if not isinstance(findings, list):
        raise WorkflowError("commit review findings must be a list")
    allowed_severity = {"critical", "high", "medium", "low"}
    allowed_disposition = {"fixed", "dismissed", "accepted", "out_of_scope"}
    normalized: list[dict[str, Any]] = []
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise WorkflowError(f"commit review finding {index} must be an object")
        if finding.get("severity") not in allowed_severity:
            raise WorkflowError(f"commit review finding {index} has an invalid severity")
        disposition = finding.get("disposition")
        if disposition not in allowed_disposition:
            raise WorkflowError(f"commit review finding {index} is not dispositioned")
        if len(str(finding.get("summary", "")).strip()) < 8:
            raise WorkflowError(f"commit review finding {index} needs a concrete summary")
        value = dict(finding)
        if disposition == "fixed":
            resolved_by = str(finding.get("resolved_by_revision", "")).lower()
            if not GIT_REVISION_RE.fullmatch(resolved_by):
                raise WorkflowError(
                    f"commit review finding {index} needs a full resolved_by_revision"
                )
            if not git_revision_is_ancestor(repository_path, commit_revision, resolved_by):
                raise WorkflowError(
                    f"commit review finding {index} resolution is not a later descendant commit"
                )
            value["resolved_by_revision"] = resolved_by
        normalized.append(value)
    return normalized


def validate_commit_review_receipt(
    receipt: dict[str, Any],
    *,
    wp_id: str,
    phase_number: int,
    require_contained: bool = True,
) -> dict[str, Any]:
    if receipt.get("schema_version") != 1 or receipt.get("template") is True:
        raise WorkflowError("commit review receipt must be an executable schema_version 1 receipt")
    expected = {
        "wp_id": wp_id,
        "phase": phase_number,
        "review_scope": "atomic-commit",
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise WorkflowError(f"commit review receipt {key} must equal {value!r}")
    review_mode = str(receipt.get("review_mode", ""))
    if review_mode == "ocr-delegation":
        # Preserve receipts written before OCR became the primary verdict.
        if receipt.get("model") != "gpt-5.6-luna":
            raise WorkflowError("legacy ocr-delegation receipts need model gpt-5.6-luna")
        if receipt.get("reasoning_effort") != "max":
            raise WorkflowError("legacy ocr-delegation receipts need reasoning_effort max")
    elif review_mode != "ocr":
        raise WorkflowError("commit review receipt review_mode must be ocr or legacy ocr-delegation")
    repository = str(receipt.get("repository", "")).strip().strip("/")
    repository_path = str(receipt.get("repository_path", "")).strip()
    parent_revision = str(receipt.get("parent_revision", "")).lower()
    commit_revision = str(receipt.get("commit_revision", "")).lower()
    reviewer_session = str(receipt.get("reviewer_session", "")).strip()
    session_id = str(receipt.get("session_id", "")).strip()
    batch_count = receipt.get("batch_count")
    synthesis = receipt.get("synthesis")
    if not REPOSITORY_SLUG_RE.fullmatch(repository):
        raise WorkflowError("commit review receipt needs a canonical repository slug")
    if not Path(repository_path).is_absolute():
        raise WorkflowError("commit review receipt repository_path must be absolute")
    if not GIT_REVISION_RE.fullmatch(parent_revision):
        raise WorkflowError("commit review receipt parent_revision must be a full Git SHA")
    if not GIT_REVISION_RE.fullmatch(commit_revision):
        raise WorkflowError("commit review receipt commit_revision must be a full Git SHA")
    if git_commit_parent(repository_path, commit_revision) != parent_revision:
        raise WorkflowError("commit review receipt parent_revision is not the commit's exact parent")
    current_revision = current_git_revision(repository_path)
    if require_contained and not git_revision_is_ancestor(
        repository_path, commit_revision, current_revision
    ):
        raise WorkflowError("commit review receipt commit is not contained by the checkout HEAD")
    if review_mode == "ocr":
        if not session_id or not re.fullmatch(r"[A-Za-z0-9-]{16,}", session_id):
            raise WorkflowError("OCR receipt needs a provider session_id")
        if not str(receipt.get("ocr_version", "")).strip() or not str(receipt.get("provider", "")).strip() or not str(receipt.get("model", "")).strip() or not str(receipt.get("effort", "")).strip():
            raise WorkflowError("OCR receipt needs ocr_version, provider, model, and effort")
        if receipt.get("terminal_state") != "complete":
            raise WorkflowError("OCR receipt terminal_state must be complete")
        preview_files = receipt.get("preview_files")
        file_statuses = receipt.get("file_statuses")
        if not isinstance(preview_files, list) or not isinstance(file_statuses, list) or not preview_files:
            raise WorkflowError("OCR receipt needs preview_files and file_statuses")
        if any(not isinstance(path, str) for path in preview_files) or any(not isinstance(item, dict) for item in file_statuses):
            raise WorkflowError("OCR receipt file coverage must be structured")
        if any(item.get("status") not in {"complete", "completed", "reviewed"} for item in file_statuses):
            raise WorkflowError("OCR receipt contains incomplete file status")
        if set(preview_files) != {str(item.get("path", "")) for item in file_statuses}:
            raise WorkflowError("OCR receipt preview and file status paths must match")
        if not str(receipt.get("rule_fingerprint", "")).strip():
            raise WorkflowError("OCR receipt needs rule_fingerprint")
    elif not re.fullmatch(r"/root/[A-Za-z0-9._/-]+", reviewer_session):
        raise WorkflowError("commit review receipt needs a canonical fresh /root/... reviewer session")
    if not isinstance(batch_count, int) or isinstance(batch_count, bool) or batch_count < 1:
        raise WorkflowError("commit review receipt batch_count must be a positive integer")
    if synthesis not in {"accepted", "resolved"}:
        raise WorkflowError("commit review receipt synthesis must be accepted or resolved")
    command_validator = validate_ocr_commands if review_mode == "ocr" else validate_delegate_commands
    commands = command_validator(receipt.get("commands"), base_revision=parent_revision, head_revision=commit_revision, repository=repository)
    findings = _validate_findings(
        receipt.get("findings"),
        repository=repository,
        commit_revision=commit_revision,
        repository_path=repository_path,
    )
    if synthesis == "resolved" and not any(
        item.get("disposition") == "fixed" for item in findings
    ):
        raise WorkflowError("resolved commit review synthesis requires a fixed finding")
    normalized = {
        **receipt,
        "repository": repository,
        "repository_path": repository_path,
        "parent_revision": parent_revision,
        "commit_revision": commit_revision,
        "reviewer_session": reviewer_session,
        "commands": commands,
        "summary": _evidence_summary(receipt.get("summary"), "commit review summary"),
        "findings": findings,
    }
    if review_mode == "ocr":
        normalized["session_id"] = session_id
    return normalized


def _receipt_digest(receipt: dict[str, Any]) -> str:
    serialized = json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def commit_review_marker(receipt: dict[str, Any]) -> str:
    return (
        f"{COMMIT_REVIEW_MARKER_PREFIX}{receipt['repository']}:"
        f"{receipt['commit_revision']}:{_receipt_digest(receipt)}"
    )


def reviewer_session_marker(reviewer_session: str) -> str:
    digest = hashlib.sha256(reviewer_session.encode("utf-8")).hexdigest()
    return REVIEWER_SESSION_MARKER_PREFIX + digest


def receipt_session_identity(receipt: dict[str, Any]) -> str:
    return str(receipt.get("reviewer_session") or receipt.get("session_id") or "")


def render_commit_review_evidence(receipt: dict[str, Any]) -> str:
    findings = receipt["findings"]
    disposition = "无 finding。" if not findings else "；".join(
        f"{item['severity']}:{item['disposition']}:{item['summary']}" for item in findings
    )
    return (
        "<h3>Commit 审查记录</h3>"
        f"<p><code>{commit_review_marker(receipt)}</code> "
        f"<code>{reviewer_session_marker(receipt_session_identity(receipt))}</code></p>"
        f"<p>仓库：<code>{html.escape(receipt['repository'])}</code>；提交："
        f"<code>{receipt['parent_revision']}..{receipt['commit_revision']}</code>；"
        f"reviewer：<code>{html.escape(receipt_session_identity(receipt))}</code>；"
        f"Batch：{receipt['batch_count']}；synthesis："
        f"<code>{receipt['synthesis']}</code>。</p>"
        f"<p>{html.escape(receipt['summary'])}</p>"
        f"<p>Findings：{html.escape(disposition)}</p>"
    )


def record_phase_commit_review(
    client: PlaneClient,
    route: dict[str, Any],
    wp_id: str,
    phase_number: int,
    receipt: dict[str, Any],
    *,
    apply: bool,
) -> dict[str, Any]:
    project = client.project()
    assert_project(route, project)
    assert_active_project(project)
    work_package, phases, _ = work_package_and_phases(client, route, wp_id)
    phase = next(
        (
            item
            for item in phases
            if str(item.get("external_id", "")).endswith(f":{phase_number}")
        ),
        None,
    )
    if phase is None:
        raise WorkflowError(f"Phase {phase_number} is not present in work-package:{wp_id}")
    normalized = validate_commit_review_receipt(
        receipt, wp_id=wp_id, phase_number=phase_number
    )
    expected_repositories = work_package_repositories(
        work_package.get("description_html") or ""
    )
    if normalized["repository"] not in expected_repositories:
        raise WorkflowError(
            "commit review receipt repository is not declared by the Work Package"
        )
    marker = commit_review_marker(normalized)
    session_marker = reviewer_session_marker(receipt_session_identity(normalized))
    current_html = str(phase.get("description_html") or "")
    already_recorded = marker in current_html
    commit_prefix = (
        f"{COMMIT_REVIEW_MARKER_PREFIX}{normalized['repository']}:"
        f"{normalized['commit_revision']}:"
    )
    recorded_elsewhere = any(
        item["id"] != phase["id"]
        and commit_prefix in str(item.get("description_html") or "")
        for item in phases
    )
    if recorded_elsewhere:
        raise WorkflowError("commit review evidence is already recorded on another Phase")
    if not already_recorded and any(
        session_marker in str(item.get("description_html") or "") for item in phases
    ):
        raise WorkflowError("reviewer session was already used by another commit in this Work Package")
    final_html = (
        current_html
        if already_recorded
        else current_html + render_commit_review_evidence(normalized)
    )
    action = None if already_recorded else {
        "work_item_id": phase["id"],
        "phase": phase_number,
        "commit_revision": normalized["commit_revision"],
    }
    if apply and action:
        client.request(
            "PATCH",
            f"{client.project_prefix}/work-items/{phase['id']}",
            data={"description_html": final_html},
        )
        reread = client.retrieve_work_item(phase["id"])
        if marker not in str(reread.get("description_html") or ""):
            raise WorkflowError("Phase commit review evidence PATCH was not confirmed by re-read")
    return {
        "action": action,
        "already_recorded": already_recorded,
        "applied": apply,
        "verified": already_recorded or (apply and action is not None),
        "work_package": f"work-package:{wp_id}",
    }


def validate_history_rewrite_receipt(
    receipt: dict[str, Any],
    *,
    wp_id: str,
    phase_number: int,
    require_current_head: bool = True,
) -> dict[str, Any]:
    if receipt.get("schema_version") != 1 or receipt.get("template") is True:
        raise WorkflowError("history rewrite receipt must be an executable schema_version 1 receipt")
    expected = {
        "wp_id": wp_id,
        "phase": phase_number,
        "operation": "feature-autosquash",
        "result": "history-only",
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise WorkflowError(f"history rewrite receipt {key} must equal {value!r}")

    repository = str(receipt.get("repository", "")).strip().strip("/")
    repository_path = str(receipt.get("repository_path", "")).strip()
    original_parent = str(receipt.get("original_parent_revision", "")).lower()
    reviewed_head = str(receipt.get("reviewed_head_revision", "")).lower()
    final_parent = str(receipt.get("final_parent_revision", "")).lower()
    final_commit = str(receipt.get("final_commit_revision", "")).lower()
    reviewed_tree = str(receipt.get("reviewed_tree_revision", "")).lower()
    final_tree = str(receipt.get("final_tree_revision", "")).lower()
    if not REPOSITORY_SLUG_RE.fullmatch(repository):
        raise WorkflowError("history rewrite receipt needs a canonical repository slug")
    if not Path(repository_path).is_absolute():
        raise WorkflowError("history rewrite receipt repository_path must be absolute")
    if git_repository_slug(repository_path) != repository:
        raise WorkflowError("history rewrite repository does not match repository_path")
    revisions = (
        original_parent,
        reviewed_head,
        final_parent,
        final_commit,
        reviewed_tree,
        final_tree,
    )
    if any(not GIT_REVISION_RE.fullmatch(value) for value in revisions):
        raise WorkflowError("history rewrite receipt revisions must be full Git SHAs")
    if final_parent != original_parent:
        raise WorkflowError("history rewrite must preserve the feature commit parent")
    if git_commit_parent(repository_path, final_commit) != final_parent:
        raise WorkflowError("history rewrite final parent does not match the final commit")
    current_revision = current_git_revision(repository_path)
    if require_current_head and current_revision != final_commit:
        raise WorkflowError("history rewrite must be recorded immediately at the squashed HEAD")
    if not require_current_head and not git_revision_is_ancestor(
        repository_path, final_commit, current_revision
    ):
        raise WorkflowError("history rewrite final commit is not contained by the checkout HEAD")

    original_commits = receipt.get("original_commits")
    if not isinstance(original_commits, list) or len(original_commits) < 2:
        raise WorkflowError("history rewrite needs one feature commit and at least one fixup commit")
    normalized_commits = []
    expected_parent = original_parent
    feature_subject = ""
    for index, item in enumerate(original_commits):
        if not isinstance(item, dict):
            raise WorkflowError(f"history rewrite original commit {index} must be an object")
        commit = str(item.get("commit_revision", "")).lower()
        parent = str(item.get("parent_revision", "")).lower()
        role = str(item.get("role", ""))
        review_receipt = item.get("review_receipt")
        expected_role = "feature" if index == 0 else "fixup"
        if role != expected_role:
            raise WorkflowError(
                f"history rewrite original commit {index} role must be {expected_role}"
            )
        if not GIT_REVISION_RE.fullmatch(commit) or not GIT_REVISION_RE.fullmatch(parent):
            raise WorkflowError("history rewrite original commits need full Git SHAs")
        if not isinstance(review_receipt, dict):
            raise WorkflowError("history rewrite original commit needs its complete review receipt")
        normalized_review = validate_commit_review_receipt(
            review_receipt,
            wp_id=wp_id,
            phase_number=phase_number,
            require_contained=False,
        )
        if (
            normalized_review["repository"] != repository
            or normalized_review["repository_path"] != repository_path
            or normalized_review["parent_revision"] != parent
            or normalized_review["commit_revision"] != commit
        ):
            raise WorkflowError("history rewrite original review receipt does not match its commit")
        if parent != expected_parent or git_commit_parent(repository_path, commit) != parent:
            raise WorkflowError("history rewrite original commit chain is not contiguous")
        subject = git_commit_subject(repository_path, commit)
        if index == 0:
            if subject.startswith(("fixup! ", "squash! ", "amend! ")):
                raise WorkflowError("history rewrite feature commit cannot itself be a fixup")
            feature_subject = subject
        elif subject != f"fixup! {feature_subject}":
            raise WorkflowError("history rewrite fixup does not target the feature commit")
        normalized_commits.append(
            {
                "commit_revision": commit,
                "parent_revision": parent,
                "role": role,
                "review_receipt": normalized_review,
            }
        )
        expected_parent = commit
    if reviewed_head != expected_parent:
        raise WorkflowError("history rewrite reviewed head must be the final fixup commit")
    if final_commit in {item["commit_revision"] for item in normalized_commits}:
        raise WorkflowError("history rewrite final commit must be distinct from original commits")
    if git_commit_subject(repository_path, final_commit) != feature_subject:
        raise WorkflowError("history rewrite final commit must preserve the feature subject")

    actual_reviewed_tree = git_tree_revision(repository_path, reviewed_head)
    actual_final_tree = git_tree_revision(repository_path, final_commit)
    if reviewed_tree != actual_reviewed_tree or final_tree != actual_final_tree:
        raise WorkflowError("history rewrite receipt tree revisions do not match Git")
    if reviewed_tree != final_tree:
        raise WorkflowError("history rewrite changed the reviewed source tree")

    commands = receipt.get("verification_commands")
    if (
        not isinstance(commands, list)
        or len(commands) < 2
        or any(not isinstance(command, str) or len(command.strip()) < 8 for command in commands)
    ):
        raise WorkflowError("history rewrite receipt needs concrete verification commands")
    operator = str(receipt.get("operator", "")).strip()
    if len(operator) < 2:
        raise WorkflowError("history rewrite receipt needs an operator")
    recorded_at = str(receipt.get("recorded_at", "")).strip()
    try:
        timestamp = dt.datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise WorkflowError("history rewrite receipt recorded_at must be ISO-8601") from error
    if timestamp.tzinfo is None:
        raise WorkflowError("history rewrite receipt recorded_at must include a timezone")
    return {
        **receipt,
        "repository": repository,
        "repository_path": repository_path,
        "original_parent_revision": original_parent,
        "reviewed_head_revision": reviewed_head,
        "original_commits": normalized_commits,
        "final_parent_revision": final_parent,
        "final_commit_revision": final_commit,
        "reviewed_tree_revision": reviewed_tree,
        "final_tree_revision": final_tree,
        "verification_commands": [command.strip() for command in commands],
        "operator": operator,
        "recorded_at": timestamp.isoformat(),
        "summary": _evidence_summary(receipt.get("summary"), "history rewrite summary"),
    }


def history_rewrite_marker(receipt: dict[str, Any]) -> str:
    return (
        f"{HISTORY_REWRITE_MARKER_PREFIX}{receipt['repository']}:"
        f"{receipt['final_commit_revision']}:{_receipt_digest(receipt)}"
    )


def render_history_rewrite_evidence(receipt: dict[str, Any]) -> str:
    original = ", ".join(
        f"{item['role']}:{item['commit_revision']}" for item in receipt["original_commits"]
    )
    return (
        "<h3>History-only feature autosquash</h3>"
        f"<p><code>{history_rewrite_marker(receipt)}</code></p>"
        f"<p>仓库：<code>{html.escape(receipt['repository'])}</code>；原提交："
        f"<code>{html.escape(original)}</code>；最终提交："
        f"<code>{receipt['final_parent_revision']}..{receipt['final_commit_revision']}</code>。</p>"
        f"<p>Tree equality：<code>{receipt['reviewed_tree_revision']}</code>；"
        f"operator：<code>{html.escape(receipt['operator'])}</code>；"
        f"recorded_at：<code>{html.escape(receipt['recorded_at'])}</code>。</p>"
        f"<p>{html.escape(receipt['summary'])}</p>"
    )


def record_phase_history_rewrite(
    client: PlaneClient,
    route: dict[str, Any],
    wp_id: str,
    phase_number: int,
    receipt: dict[str, Any],
    *,
    apply: bool,
) -> dict[str, Any]:
    project = client.project()
    assert_project(route, project)
    assert_active_project(project)
    work_package, phases, _ = work_package_and_phases(client, route, wp_id)
    phase = next(
        (
            item
            for item in phases
            if str(item.get("external_id", "")).endswith(f":{phase_number}")
        ),
        None,
    )
    if phase is None:
        raise WorkflowError(f"Phase {phase_number} is not present in work-package:{wp_id}")
    normalized = validate_history_rewrite_receipt(
        receipt, wp_id=wp_id, phase_number=phase_number
    )
    expected_repositories = work_package_repositories(
        work_package.get("description_html") or ""
    )
    if normalized["repository"] not in expected_repositories:
        raise WorkflowError("history rewrite repository is not declared by the Work Package")

    current_html = str(phase.get("description_html") or "")
    for item in normalized["original_commits"]:
        commit_marker = (
            commit_review_marker(item["review_receipt"])
        )
        if commit_marker not in current_html:
            raise WorkflowError(
                f"history rewrite original commit {item['commit_revision']} lacks review evidence"
            )
        if any(
            other["id"] != phase["id"]
            and commit_marker in str(other.get("description_html") or "")
            for other in phases
        ):
            raise WorkflowError("history rewrite original commit is recorded on another Phase")

    marker = history_rewrite_marker(normalized)
    final_prefix = (
        f"{HISTORY_REWRITE_MARKER_PREFIX}{normalized['repository']}:"
        f"{normalized['final_commit_revision']}:"
    )
    already_recorded = marker in current_html
    if not already_recorded and any(
        final_prefix in str(item.get("description_html") or "") for item in phases
    ):
        raise WorkflowError("history rewrite final commit already has different provenance")
    final_html = (
        current_html
        if already_recorded
        else current_html + render_history_rewrite_evidence(normalized)
    )
    action = None if already_recorded else {
        "work_item_id": phase["id"],
        "phase": phase_number,
        "final_commit_revision": normalized["final_commit_revision"],
    }
    if apply and action:
        client.request(
            "PATCH",
            f"{client.project_prefix}/work-items/{phase['id']}",
            data={"description_html": final_html},
        )
        reread = client.retrieve_work_item(phase["id"])
        if marker not in str(reread.get("description_html") or ""):
            raise WorkflowError("Phase history rewrite PATCH was not confirmed by re-read")
    return {
        "action": action,
        "already_recorded": already_recorded,
        "applied": apply,
        "verified": already_recorded or (apply and action is not None),
        "work_package": f"work-package:{wp_id}",
    }


def validate_mr_receipt(
    receipt: dict[str, Any],
    *,
    wp_id: str,
    expected_repositories: set[str],
    phases: list[dict[str, Any]],
    current_revisions: dict[str, str] | None = None,
    commit_chains: dict[str, list[tuple[str, str]]] | None = None,
) -> dict[str, Any]:
    if receipt.get("schema_version") != 1 or receipt.get("template") is True:
        raise WorkflowError("MR receipt must be an executable schema_version 1 receipt")
    if receipt.get("wp_id") != wp_id or receipt.get("result") != "opened":
        raise WorkflowError("MR receipt must match the Work Package and have result='opened'")
    merge_requests = receipt.get("merge_requests")
    if not isinstance(merge_requests, list) or not merge_requests:
        raise WorkflowError("MR receipt merge_requests must contain at least one MR")
    phase_by_number = {
        int(str(item["external_id"]).rsplit(":", 1)[1]): item for item in phases
    }
    seen_repositories: set[str] = set()
    seen_urls: set[str] = set()
    normalized_items = []
    for index, item in enumerate(merge_requests):
        if not isinstance(item, dict):
            raise WorkflowError(f"MR receipt entry {index} must be an object")
        repository = str(item.get("repository", "")).strip().strip("/")
        repository_path = str(item.get("repository_path", "")).strip()
        url = str(item.get("url", "")).strip()
        state = str(item.get("state", "")).strip()
        verification_command = str(item.get("verification_command", "")).strip()
        base_revision = str(item.get("base_revision", "")).lower()
        head_revision = str(item.get("head_revision", "")).lower()
        if not REPOSITORY_SLUG_RE.fullmatch(repository):
            raise WorkflowError(f"MR receipt entry {index} needs a repository slug")
        if repository in seen_repositories or url in seen_urls:
            raise WorkflowError("MR receipt repeats a repository or MR URL")
        if not Path(repository_path).is_absolute():
            raise WorkflowError(f"MR receipt {repository} repository_path must be absolute")
        if not MERGE_REQUEST_URL_RE.fullmatch(url) or merge_request_repository(url) != repository:
            raise WorkflowError(f"MR receipt {repository} needs a matching real GitLab MR URL")
        if state != "opened":
            raise WorkflowError(f"MR receipt {repository} state must be 'opened'")
        if len(verification_command) < 8:
            raise WorkflowError(
                f"MR receipt {repository} needs the command used to re-read the MR"
            )
        if not GIT_REVISION_RE.fullmatch(base_revision) or not GIT_REVISION_RE.fullmatch(head_revision):
            raise WorkflowError(f"MR receipt {repository} revisions must be full Git SHAs")
        current_revision = (
            current_revisions.get(repository_path)
            if current_revisions is not None
            else current_git_revision(repository_path)
        )
        if current_revision != head_revision:
            raise WorkflowError(f"MR receipt {repository} head does not match its checkout HEAD")
        chain = (
            commit_chains.get(repository_path)
            if commit_chains is not None
            else git_commit_chain(repository_path, base_revision, head_revision)
        )
        if not chain:
            raise WorkflowError(f"MR receipt {repository} has an empty commit chain")
        commit_map = item.get("commits")
        if not isinstance(commit_map, list) or len(commit_map) != len(chain):
            raise WorkflowError(f"MR receipt {repository} must map every commit to one Phase")
        normalized_commits = []
        for position, ((parent, commit), mapped) in enumerate(zip(chain, commit_map)):
            if not isinstance(mapped, dict):
                raise WorkflowError(f"MR receipt {repository} commit mapping {position} must be an object")
            mapped_commit = str(mapped.get("commit_revision", "")).lower()
            phase_number = mapped.get("phase")
            if (
                mapped_commit != commit
                or not isinstance(phase_number, int)
                or isinstance(phase_number, bool)
                or phase_number not in phase_by_number
            ):
                raise WorkflowError(
                    f"MR receipt {repository} commit mapping {position} does not match the Git chain or a Phase"
                )
            phase_html = str(phase_by_number[phase_number].get("description_html") or "")
            rewrite_pattern = re.escape(
                f"{HISTORY_REWRITE_MARKER_PREFIX}{repository}:{commit}:"
            ) + r"[0-9a-f]{64}"
            direct_receipt = mapped.get("commit_review_receipt")
            direct_review = isinstance(direct_receipt, dict)
            if direct_review:
                normalized_review = validate_commit_review_receipt(
                    direct_receipt,
                    wp_id=wp_id,
                    phase_number=phase_number,
                    require_contained=False,
                )
                if (
                    normalized_review["repository"] != repository
                    or not git_paths_share_common_directory(
                        normalized_review["repository_path"], repository_path
                    )
                    or normalized_review["parent_revision"] != parent
                    or normalized_review["commit_revision"] != commit
                    or commit_review_marker(normalized_review) not in phase_html
                ):
                    raise WorkflowError(
                        f"MR receipt {repository} commit {commit} has invalid review evidence"
                    )
            if not direct_review:
                rewrite_receipt = mapped.get("history_rewrite_receipt")
                if not isinstance(rewrite_receipt, dict):
                    raise WorkflowError(
                        f"MR receipt {repository} commit {commit} needs its history rewrite receipt"
                    )
                normalized_rewrite = validate_history_rewrite_receipt(
                    rewrite_receipt,
                    wp_id=wp_id,
                    phase_number=phase_number,
                    require_current_head=False,
                )
                if (
                    normalized_rewrite["repository"] != repository
                    or not git_paths_share_common_directory(
                        normalized_rewrite["repository_path"], repository_path
                    )
                    or normalized_rewrite["final_commit_revision"] != commit
                    or history_rewrite_marker(normalized_rewrite) not in phase_html
                    or re.search(rewrite_pattern, phase_html) is None
                ):
                    raise WorkflowError(
                        f"MR receipt {repository} commit {commit} has invalid history rewrite evidence"
                    )
            if not direct_review and re.search(rewrite_pattern, phase_html) is None:
                raise WorkflowError(
                    f"MR receipt {repository} commit {commit} lacks review or history rewrite evidence in Phase {phase_number}"
                )
            normalized_mapping = {
                "commit_revision": commit,
                "parent_revision": parent,
                "phase": phase_number,
            }
            if direct_review:
                normalized_mapping["commit_review_receipt"] = normalized_review
            else:
                normalized_mapping["history_rewrite_receipt"] = normalized_rewrite
            normalized_commits.append(normalized_mapping)
        seen_repositories.add(repository)
        seen_urls.add(url)
        normalized_items.append(
            {
                **item,
                "repository": repository,
                "repository_path": repository_path,
                "url": url,
                "state": state,
                "verification_command": verification_command,
                "base_revision": base_revision,
                "head_revision": head_revision,
                "commits": normalized_commits,
            }
        )
    if seen_repositories != expected_repositories:
        missing = sorted(expected_repositories - seen_repositories)
        unexpected = sorted(seen_repositories - expected_repositories)
        raise WorkflowError(
            "MR receipt repository set does not match the Work Package; "
            f"missing={missing}, unexpected={unexpected}"
        )
    return {
        **receipt,
        "merge_requests": sorted(normalized_items, key=lambda item: item["repository"]),
        "summary": _evidence_summary(receipt.get("summary"), "MR receipt summary"),
    }


def mr_set_digest(receipt: dict[str, Any]) -> str:
    identity = [
        {
            key: item[key]
            for key in ("repository", "url", "base_revision", "head_revision")
        }
        for item in receipt["merge_requests"]
    ]
    serialized = json.dumps(identity, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def mr_set_marker(receipt: dict[str, Any]) -> str:
    return WP_MR_MARKER_PREFIX + mr_set_digest(receipt)


def render_mr_evidence(receipt: dict[str, Any]) -> str:
    merge_requests = "".join(
        "<li>"
        f"<code>{html.escape(item['repository'])}</code>："
        f"<a href=\"{html.escape(item['url'], quote=True)}\">{html.escape(item['url'])}</a>；"
        f"<code>{item['base_revision']}..{item['head_revision']}</code>；"
        f"commits={len(item['commits'])}"
        "</li>"
        for item in receipt["merge_requests"]
    )
    return (
        "<h3>Merge Requests</h3>"
        f"<p><code>{mr_set_marker(receipt)}</code></p>"
        f"<p>MR 数：{len(receipt['merge_requests'])}；WP Review 表示这些 MR 已创建，"
        "不表示执行 WP 级对抗审查。</p>"
        f"<ul>{merge_requests}</ul>"
        f"<p>{html.escape(receipt['summary'])}</p>"
    )


def start_work_package_review(
    client: PlaneClient,
    route: dict[str, Any],
    wp_id: str,
    receipt: dict[str, Any],
    *,
    apply: bool,
) -> dict[str, Any]:
    project = client.project()
    assert_project(route, project)
    assert_active_project(project)
    states = client.states()
    completed = resolve_state(states, "completed")
    review = resolve_state(states, "review")
    work_package, phases, _ = work_package_and_phases(client, route, wp_id)
    assert_phases_ready_for_wp_review(phases, completed["id"])
    if object_id(work_package.get("state")) == completed["id"]:
        raise WorkflowError("Work Package is already Done")
    expected_repositories = work_package_repositories(
        work_package.get("description_html") or ""
    )
    normalized = validate_mr_receipt(
        receipt,
        wp_id=wp_id,
        expected_repositories=expected_repositories,
        phases=phases,
    )
    marker = mr_set_marker(normalized)
    current_html = work_package.get("description_html") or ""
    already_recorded = marker in current_html
    already_review = object_id(work_package.get("state")) == review["id"]
    final_html = current_html if already_recorded else current_html + render_mr_evidence(normalized)
    action = None if already_recorded and already_review else {
        "work_item_id": work_package["id"],
        "state_id": review["id"],
        "mr_set": mr_set_digest(normalized),
        "merge_requests": [item["url"] for item in normalized["merge_requests"]],
    }
    if apply and action:
        client.request(
            "PATCH",
            f"{client.project_prefix}/work-items/{work_package['id']}",
            data={"description_html": final_html, "state": review["id"]},
        )
        reread = client.retrieve_work_item(work_package["id"])
        if (
            marker not in str(reread.get("description_html", ""))
            or object_id(reread.get("state")) != review["id"]
        ):
            raise WorkflowError("Work Package MR record and Review state were not confirmed by re-read")
    return {
        "action": action,
        "already_recorded": already_recorded,
        "already_review": already_review,
        "applied": apply,
        "phase_count": len(phases),
        "verified": (already_recorded and already_review) or (apply and action is not None),
        "work_package": f"work-package:{wp_id}",
    }


def migrate_legacy_work_package_repositories(
    client: PlaneClient,
    route: dict[str, Any],
    wp_id: str,
    repositories: list[str],
    *,
    apply: bool,
) -> dict[str, Any]:
    """Backfill only missing WP repository metadata while preserving Phase evidence."""
    project = client.project()
    assert_project(route, project)
    assert_active_project(project)
    work_package, phases, _ = work_package_and_phases(client, route, wp_id)
    current_html = str(work_package.get("description_html") or "")
    final_html, changed = append_legacy_work_package_repositories(current_html, repositories)
    phase_snapshot = [
        (item["id"], item.get("state"), item.get("description_html")) for item in phases
    ]
    action = None if not changed else {
        "work_item_id": work_package["id"],
        "repositories": sorted(set(repositories)),
        "preserves_phase_evidence": True,
    }
    if apply and action:
        client.request(
            "PATCH",
            f"{client.project_prefix}/work-items/{work_package['id']}",
            data={"description_html": final_html},
        )
        reread = client.retrieve_work_item(work_package["id"])
        reread_html = str(reread.get("description_html") or "")
        try:
            reread_repositories = work_package_repositories(reread_html)
        except WorkflowError as error:
            raise WorkflowError("legacy repository migration was not confirmed by re-read") from error
        if reread_repositories != set(repositories):
            raise WorkflowError("legacy repository migration repository set was not confirmed by re-read")
        _, reread_phases, _ = work_package_and_phases(client, route, wp_id)
        reread_snapshot = [
            (item["id"], item.get("state"), item.get("description_html"))
            for item in reread_phases
        ]
        if reread_snapshot != phase_snapshot:
            raise WorkflowError("legacy repository migration changed Phase state or evidence")
    return {
        "action": action,
        "applied": apply,
        "changed": changed,
        "phase_count": len(phases),
        "verified": not changed or (apply and action is not None),
        "work_package": f"work-package:{wp_id}",
    }


def validate_merge_receipt(
    receipt: dict[str, Any],
    *,
    wp_id: str,
    expected_repositories: set[str],
    target_revisions: dict[str, str] | None = None,
    ancestry_results: dict[tuple[str, str, str], bool] | None = None,
) -> dict[str, Any]:
    if receipt.get("schema_version") != 1 or receipt.get("template") is True:
        raise WorkflowError("merge receipt must be an executable schema_version 1 receipt")
    if receipt.get("wp_id") != wp_id or receipt.get("result") != "merged":
        raise WorkflowError("merge receipt must match the Work Package and have result='merged'")
    merge_requests = receipt.get("merge_requests")
    if not isinstance(merge_requests, list) or not merge_requests:
        raise WorkflowError("merge receipt must contain at least one merged MR")
    seen_repositories: set[str] = set()
    seen_urls: set[str] = set()
    normalized_items = []
    for index, item in enumerate(merge_requests):
        if not isinstance(item, dict):
            raise WorkflowError(f"merge receipt entry {index} must be an object")
        repository = str(item.get("repository", "")).strip().strip("/")
        url = str(item.get("url", "")).strip()
        base_revision = str(item.get("base_revision", "")).lower()
        head_revision = str(item.get("head_revision", "")).lower()
        target_path = str(item.get("target_repository_path", "")).strip()
        merge_revision = str(item.get("merge_revision", "")).lower()
        squash_revision = str(item.get("squash_revision") or "").lower()
        merge_method = str(item.get("merge_method", "")).strip()
        verification_command = str(item.get("verification_command", "")).strip()
        if not REPOSITORY_SLUG_RE.fullmatch(repository):
            raise WorkflowError(f"merge receipt entry {index} needs a repository slug")
        if repository in seen_repositories or url in seen_urls:
            raise WorkflowError("merge receipt repeats a repository or MR URL")
        if not MERGE_REQUEST_URL_RE.fullmatch(url) or merge_request_repository(url) != repository:
            raise WorkflowError(f"merge receipt {repository} needs a matching real GitLab MR URL")
        if not GIT_REVISION_RE.fullmatch(base_revision) or not GIT_REVISION_RE.fullmatch(head_revision):
            raise WorkflowError(f"merge receipt {repository} source revisions must be full Git SHAs")
        if item.get("state") != "merged":
            raise WorkflowError(f"merge receipt {repository} state must be 'merged'")
        if not Path(target_path).is_absolute():
            raise WorkflowError(f"merge receipt {repository} target_repository_path must be absolute")
        if not GIT_REVISION_RE.fullmatch(merge_revision):
            raise WorkflowError(f"merge receipt {repository} merge_revision must be a full Git SHA")
        if merge_method not in {"merge", "fast_forward", "squash"}:
            raise WorkflowError(
                f"merge receipt {repository} merge_method must be merge, fast_forward, or squash"
            )
        current_target = (
            target_revisions.get(target_path)
            if target_revisions is not None
            else current_git_revision(target_path)
        )
        if current_target != merge_revision:
            raise WorkflowError(
                f"merge receipt {repository} merge_revision does not match target checkout HEAD"
            )
        ancestry_revision = head_revision
        if merge_method == "squash":
            if not GIT_REVISION_RE.fullmatch(squash_revision):
                raise WorkflowError(
                    f"merge receipt {repository} squash merge needs a full squash_revision"
                )
            ancestry_revision = squash_revision
        elif squash_revision:
            raise WorkflowError(
                f"merge receipt {repository} must omit squash_revision for {merge_method}"
            )
        ancestry_key = (target_path, ancestry_revision, merge_revision)
        is_ancestor = (
            ancestry_results.get(ancestry_key)
            if ancestry_results is not None
            else git_revision_is_ancestor(target_path, ancestry_revision, merge_revision)
        )
        if is_ancestor is not True:
            raise WorkflowError(
                f"merge receipt {repository} integrated revision is not contained by the merge revision"
            )
        if len(verification_command) < 8:
            raise WorkflowError(
                f"merge receipt {repository} needs the glab command used to re-read merged state"
            )
        seen_repositories.add(repository)
        seen_urls.add(url)
        normalized_items.append(
            {
                **item,
                "repository": repository,
                "url": url,
                "base_revision": base_revision,
                "head_revision": head_revision,
                "target_repository_path": target_path,
                "merge_revision": merge_revision,
                "merge_method": merge_method,
                "squash_revision": squash_revision or None,
                "verification_command": verification_command,
            }
        )
    if seen_repositories != expected_repositories:
        missing = sorted(expected_repositories - seen_repositories)
        unexpected = sorted(seen_repositories - expected_repositories)
        raise WorkflowError(
            "merge receipt repository set does not match the Work Package; "
            f"missing={missing}, unexpected={unexpected}"
        )
    verification = receipt.get("final_verification")
    if not isinstance(verification, dict):
        raise WorkflowError("merge receipt final_verification must be an object")
    commands = verification.get("commands")
    if not isinstance(commands, list) or not commands or any(
        not isinstance(item, str) or not item.strip() for item in commands
    ):
        raise WorkflowError("merge receipt final_verification.commands must contain actual commands")
    real_usage = str(verification.get("real_usage", "")).strip()
    if len(real_usage) < 16:
        raise WorkflowError("merge receipt final_verification.real_usage needs an actual result")
    normalized_verification = {
        **verification,
        "commands": commands,
        "real_usage": real_usage,
        "summary": _evidence_summary(
            verification.get("summary"), "post-merge verification summary"
        ),
    }
    return {
        **receipt,
        "merge_requests": sorted(normalized_items, key=lambda item: item["repository"]),
        "final_verification": normalized_verification,
        "summary": _evidence_summary(receipt.get("summary"), "merge receipt summary"),
    }


def merge_set_marker(receipt: dict[str, Any]) -> str:
    identity = [
        {
            key: item[key]
            for key in (
                "repository",
                "url",
                "base_revision",
                "head_revision",
                "merge_revision",
            )
        }
        for item in receipt["merge_requests"]
    ]
    serialized = json.dumps(identity, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return WP_MERGE_MARKER_PREFIX + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def render_merge_evidence(receipt: dict[str, Any]) -> str:
    items = "".join(
        "<li>"
        f"<code>{html.escape(item['repository'])}</code>："
        f"<a href=\"{html.escape(item['url'], quote=True)}\">{html.escape(item['url'])}</a>；"
        f"merged=<code>{item['merge_revision']}</code>"
        "</li>"
        for item in receipt["merge_requests"]
    )
    return (
        "<h3>MR 合并与最终验证</h3>"
        f"<p><code>{merge_set_marker(receipt)}</code></p>"
        f"<ul>{items}</ul>"
        f"<p>{html.escape(receipt['summary'])}</p>"
        f"<p>真实 usage：{html.escape(receipt['final_verification']['real_usage'])}</p>"
        f"<p>{html.escape(receipt['final_verification']['summary'])}</p>"
    )


def close_work_package(
    client: PlaneClient,
    route: dict[str, Any],
    wp_id: str,
    receipt: dict[str, Any],
    *,
    apply: bool,
) -> dict[str, Any]:
    project = client.project()
    assert_project(route, project)
    assert_active_project(project)
    states = client.states()
    completed = resolve_state(states, "completed")
    review = resolve_state(states, "review")
    work_package, phases, items = work_package_and_phases(client, route, wp_id)
    assert_phases_ready_for_wp_review(phases, completed["id"])
    if object_id(work_package.get("state")) != review["id"]:
        raise WorkflowError("cannot close Work Package before its Review state gate passes")
    expected_repositories = work_package_repositories(
        work_package.get("description_html") or ""
    )
    normalized = validate_merge_receipt(
        receipt, wp_id=wp_id, expected_repositories=expected_repositories
    )
    current_html = str(work_package.get("description_html", ""))
    if mr_set_marker(normalized) not in current_html:
        raise WorkflowError(
            "cannot close Work Package before the same MR set is recorded on the WP"
        )
    merge_marker = merge_set_marker(normalized)
    final_html = (
        current_html
        if merge_marker in current_html
        else current_html + render_merge_evidence(normalized)
    )

    containing_modules: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for module in client.modules():
        membership = client.module_work_items(module["id"])
        if any(item["id"] == work_package["id"] for item in membership):
            containing_modules.append((module, membership))
    if len(containing_modules) > 1:
        raise WorkflowError("Work Package belongs to more than one Module")

    module_action: dict[str, Any] | None = None
    requirement_action: dict[str, Any] | None = None
    if containing_modules:
        module, membership = containing_modules[0]
        member_ids = {item["id"] for item in membership}
        requirement_id = object_id(work_package.get("parent"))
        if requirement_id is None:
            raise WorkflowError("Work Package has no Requirement parent; refusing Module completion")
        requirement = next((item for item in items if item["id"] == requirement_id), None)
        if requirement is None or requirement_id not in member_ids:
            raise WorkflowError("Requirement parent is missing from the Work Package Module")
        validate_closure_module_identity(route, requirement, module)
        requirement_children = [
            item
            for item in items
            if object_id(item.get("parent")) == requirement_id
        ]
        if any(item["id"] not in member_ids for item in requirement_children):
            raise WorkflowError("Module membership omits one or more Requirement children")
        other_unfinished: list[str] = []
        for sibling in requirement_children:
            if sibling["id"] == work_package["id"]:
                continue
            sibling_name = sibling.get("external_id") or sibling.get("name") or sibling["id"]
            sibling_phases = [
                client.retrieve_work_item(item["id"])
                for item in items
                if object_id(item.get("parent")) == sibling["id"]
            ]
            if object_id(sibling.get("state")) != completed["id"] or not sibling_phases:
                other_unfinished.append(str(sibling_name))
                continue
            if any(not phase_has_closure_evidence(item, completed["id"]) for item in sibling_phases):
                other_unfinished.append(str(sibling_name))
        if not other_unfinished:
            requirement_action = {"work_item_id": requirement_id, "state_id": completed["id"]}
            module_action = {"module_id": module["id"], "status": "completed"}

    if apply:
        client.request(
            "PATCH",
            f"{client.project_prefix}/work-items/{work_package['id']}",
            data={"description_html": final_html, "state": completed["id"]},
        )
        reread = client.retrieve_work_item(work_package["id"])
        if (
            object_id(reread.get("state")) != completed["id"]
            or merge_marker not in str(reread.get("description_html", ""))
        ):
            raise WorkflowError("Work Package completion PATCH was not confirmed by re-read")
        if module_action:
            assert requirement_action is not None
            client.request(
                "PATCH",
                f"{client.project_prefix}/work-items/{requirement_action['work_item_id']}",
                data={"state": requirement_action["state_id"]},
            )
            requirement = client.retrieve_work_item(requirement_action["work_item_id"])
            if object_id(requirement.get("state")) != completed["id"]:
                raise WorkflowError("Requirement completion PATCH was not confirmed by re-read")
            client.request(
                "PATCH",
                f"{client.project_prefix}/modules/{module_action['module_id']}",
                data={"status": "completed"},
            )
            module = client.retrieve_module(module_action["module_id"])
            if module.get("status") != "completed":
                raise WorkflowError("Module completion PATCH was not confirmed by re-read")
    return {
        "applied": apply,
        "verified": apply,
        "work_package_action": {
            "work_item_id": work_package["id"],
            "state_id": completed["id"],
        },
        "module_action": module_action,
        "requirement_action": requirement_action,
        "phase_count": len(phases),
    }


def _legacy_name(name: str, mode: str) -> str:
    marker = "[历史已完成]" if mode == "historical" else "[已取代]"
    if " · " in name:
        identifier, title = name.split(" · ", 1)
        title = re.sub(r"^\[(?:历史已完成|已取代)\]\s*", "", title)
        return f"{identifier} · {marker} {title}"
    value = re.sub(r"^\[(?:历史已完成|已取代)\]\s*", "", name)
    return f"{marker} {value}"


def _legacy_marker(mode: str, successor: str) -> str:
    normalized = re.sub(r"\s+", "", successor)
    return f"plane-workflow:legacy:{mode}:{normalized}"


def _append_legacy_html(
    current: str | None, *, mode: str, successor: str, reason: str
) -> str:
    value = current or ""
    marker = _legacy_marker(mode, successor)
    if marker in value:
        return value
    heading = "历史完成说明" if mode == "historical" else "取代说明"
    return (
        value.rstrip()
        + f"<h3>{heading}</h3><p><code>{html.escape(marker)}</code> "
        + f"{html.escape(reason)} 后续权威：<code>{html.escape(successor)}</code>。</p>"
    )


def _append_legacy_text(
    current: str | None, *, mode: str, successor: str, reason: str
) -> str:
    value = (current or "").rstrip()
    marker = _legacy_marker(mode, successor)
    if marker in value:
        return value
    note = f"[{marker}] {reason} 后续权威：{successor}。"
    return f"{value}\n\n{note}" if value else note


def retire_empty_module(
    client: PlaneClient,
    route: dict[str, Any],
    module_id: str,
    *,
    successor: str,
    reason: str,
    apply: bool,
) -> dict[str, Any]:
    """Cancel one empty, never-started Module after its WPs were regrouped."""

    module_id = module_id.strip()
    successor = successor.strip()
    reason = reason.strip()
    if not module_id or any(character.isspace() for character in module_id):
        raise WorkflowError("module-id must be a stable Requirement ID")
    if not LEGACY_SUCCESSOR_RE.fullmatch(successor):
        raise WorkflowError("successor must be a stable Requirement ID, optionally followed by / WP-XXA")
    if len(reason) < 8:
        raise WorkflowError("retirement reason must be at least 8 characters")

    project = client.project()
    assert_project(route, project)
    assert_active_project(project)
    external_id = f"module:{module_id}"
    matches = [
        module
        for module in client.modules()
        if module.get("external_source") == route["external_source"]
        and module.get("external_id") == external_id
    ]
    if len(matches) != 1:
        raise WorkflowError(f"expected exactly one {external_id} Module")
    module = client.retrieve_module(matches[0]["id"])
    membership = client.module_work_items(module["id"])
    if membership:
        raise WorkflowError(
            f"cannot retire non-empty {external_id}; membership count={len(membership)}"
        )

    desired = {
        "name": _legacy_name(str(module.get("name") or ""), "superseded"),
        "description": _append_legacy_text(
            module.get("description"),
            mode="superseded",
            successor=successor,
            reason=reason,
        ),
        "status": "cancelled",
    }
    changes = {
        key: value for key, value in desired.items() if module.get(key) != value
    }
    if module.get("status") not in {"planned", "cancelled"}:
        raise WorkflowError(
            f"cannot retire {external_id} from status {module.get('status')!r}"
        )
    if module.get("status") == "cancelled" and changes:
        raise WorkflowError(
            f"cancelled {external_id} does not carry the expected retirement identity"
        )

    action = None if not changes else {
        "kind": "module",
        "id": module["id"],
        "external_id": external_id,
        "fields": sorted(changes),
        "status": "cancelled",
    }
    if apply and action:
        client.request(
            "PATCH",
            f"{client.project_prefix}/modules/{module['id']}",
            data=changes,
        )
        reread = client.retrieve_module(module["id"])
        drift = {
            key: value for key, value in desired.items() if reread.get(key) != value
        }
        if drift:
            raise WorkflowError(
                f"empty Module retirement PATCH was not confirmed: {external_id}"
            )
        if client.module_work_items(module["id"]):
            raise WorkflowError(f"retired {external_id} gained unexpected membership")

    return {
        "action": action,
        "applied": apply,
        "module": external_id,
        "successor": successor,
        "verified": not changes or (apply and action is not None),
    }


def mark_legacy_work_package(
    client: PlaneClient,
    route: dict[str, Any],
    wp_id: str,
    *,
    mode: str,
    successor: str,
    reason: str,
    apply: bool,
) -> dict[str, Any]:
    """Mark one single-WP Module historical or superseded without deleting Phase evidence."""

    if mode not in {"historical", "superseded"}:
        raise WorkflowError(f"unknown legacy mode {mode!r}")
    successor = successor.strip()
    reason = reason.strip()
    if not LEGACY_SUCCESSOR_RE.fullmatch(successor):
        raise WorkflowError(
            "successor must be a stable Requirement ID, optionally followed by / WP-XXA"
        )
    if len(reason) < 8:
        raise WorkflowError("legacy reason must be at least 8 characters")

    project = client.project()
    assert_project(route, project)
    assert_active_project(project)
    states = client.states()
    completed = resolve_state(states, "completed")
    cancelled = resolve_state(states, "cancelled") if mode == "superseded" else None
    items = client.work_items()
    work_package = _match_unique(
        items,
        external_source=route["external_source"],
        external_id=f"work-package:{wp_id}",
        name=wp_id,
    )
    if work_package is None:
        raise WorkflowError(f"cannot find work-package:{wp_id}")
    work_package = client.retrieve_work_item(work_package["id"])

    requirement_id = object_id(work_package.get("parent"))
    if requirement_id is None:
        raise WorkflowError("Work Package has no Requirement parent")
    requirement = next((item for item in items if item["id"] == requirement_id), None)
    if requirement is None:
        raise WorkflowError("Work Package Requirement parent is missing")
    requirement = client.retrieve_work_item(requirement_id)
    requirement_children = [
        item for item in items if object_id(item.get("parent")) == requirement_id
    ]
    if len(requirement_children) != 1 or requirement_children[0]["id"] != work_package["id"]:
        raise WorkflowError(
            "legacy marking requires a Requirement with exactly one direct Work Package"
        )

    module_memberships: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    containing_modules: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for candidate in client.modules():
        membership = client.module_work_items(candidate["id"])
        module_memberships.append((candidate, membership))
        member_ids = {item["id"] for item in membership}
        if work_package["id"] in member_ids or requirement_id in member_ids:
            if not {work_package["id"], requirement_id}.issubset(member_ids):
                raise WorkflowError(
                    "legacy Module membership contains only part of the Requirement hierarchy"
                )
            containing_modules.append((candidate, membership))
    if len(containing_modules) != 1:
        raise WorkflowError("Work Package must belong to exactly one Module")
    module, membership = containing_modules[0]
    module = client.retrieve_module(module["id"])
    validate_closure_module_identity(route, requirement, module)

    phase_candidates = [
        item
        for item in items
        if item.get("external_source") == route["external_source"]
        and str(item.get("external_id", "")).startswith(f"phase:{wp_id}:")
    ]
    detached = [
        item.get("external_id")
        for item in phase_candidates
        if object_id(item.get("parent")) != work_package["id"]
    ]
    if detached:
        raise WorkflowError(
            "Phase hierarchy drift; these items are not direct WP children: "
            + ", ".join(map(str, detached))
        )
    if not phase_candidates:
        raise WorkflowError(f"work-package:{wp_id} has no direct Phase children")
    phases = [client.retrieve_work_item(item["id"]) for item in phase_candidates]
    phases.sort(key=lambda item: int(str(item["external_id"]).rsplit(":", 1)[1]))
    member_ids = {item["id"] for item in membership}
    missing_members = [
        item.get("external_id") or item["id"]
        for item in phases
        if item["id"] not in member_ids
    ]
    if missing_members:
        raise WorkflowError(
            "legacy Module membership omits Phase children: "
            + ", ".join(map(str, missing_members))
        )
    hierarchy_ids = {requirement_id, work_package["id"], *member_ids.intersection(
        {phase["id"] for phase in phases}
    )}
    conflicting_modules = [
        candidate.get("external_id") or candidate["id"]
        for candidate, candidate_membership in module_memberships
        if candidate["id"] != module["id"]
        and hierarchy_ids.intersection(
            {item["id"] for item in candidate_membership}
        )
    ]
    if conflicting_modules:
        raise WorkflowError(
            "legacy Requirement hierarchy belongs to more than one Module: "
            + ", ".join(map(str, conflicting_modules))
        )

    completed_phases = [
        item for item in phases if object_id(item.get("state")) == completed["id"]
    ]
    invalid_completed = [
        item.get("external_id") or item["id"]
        for item in completed_phases
        if not retained_legacy_phase_has_evidence(item, completed["id"])
    ]
    if invalid_completed:
        raise WorkflowError(
            "completed legacy Phases lack checked tasks or actual evidence: "
            + ", ".join(map(str, invalid_completed))
        )
    unfinished_phases = [item for item in phases if item not in completed_phases]
    if mode == "historical" and (
        unfinished_phases or object_id(work_package.get("state")) != completed["id"]
    ):
        raise WorkflowError("historical mode requires a completed Work Package and all Phases Done")

    desired_module_status = "completed" if mode == "historical" else "cancelled"
    desired_item_state = completed["id"] if mode == "historical" else cancelled["id"]
    module_changes = {
        key: value
        for key, value in {
            "name": _legacy_name(str(module.get("name") or ""), mode),
            "description": _append_legacy_text(
                module.get("description"),
                mode=mode,
                successor=successor,
                reason=reason,
            ),
            "status": desired_module_status,
        }.items()
        if module.get(key) != value
    }
    requirement_changes = _drift(
        requirement,
        {
            "name": _legacy_name(str(requirement.get("name") or ""), mode),
            "description_html": _append_legacy_html(
                requirement.get("description_html"),
                mode=mode,
                successor=successor,
                reason=reason,
            ),
            "state": desired_item_state,
        },
    )
    work_package_changes = _drift(
        work_package,
        {
            "name": _legacy_name(str(work_package.get("name") or ""), mode),
            "description_html": _append_legacy_html(
                work_package.get("description_html"),
                mode=mode,
                successor=successor,
                reason=reason,
            ),
            "state": desired_item_state,
        },
    )

    mutation_plan: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    if mode == "superseded":
        assert cancelled is not None
        for phase in unfinished_phases:
            changes = _drift(phase, {"state": cancelled["id"]})
            if changes:
                mutation_plan.append(("work_item", phase, changes))
    if work_package_changes:
        mutation_plan.append(("work_item", work_package, work_package_changes))
    if requirement_changes:
        mutation_plan.append(("work_item", requirement, requirement_changes))
    if module_changes:
        mutation_plan.append(("module", module, module_changes))

    actions = []
    for kind, current, changes in mutation_plan:
        action = {
            "kind": kind,
            "id": current["id"],
            "external_id": current.get("external_id"),
            "fields": sorted(changes),
        }
        if "state" in changes:
            action["state_id"] = changes["state"]
        if "status" in changes:
            action["status"] = changes["status"]
        actions.append(action)

    if apply:
        for kind, current, changes in mutation_plan:
            suffix = (
                f"{client.project_prefix}/modules/{current['id']}"
                if kind == "module"
                else f"{client.project_prefix}/work-items/{current['id']}"
            )
            client.request("PATCH", suffix, data=changes)
            reread = (
                client.retrieve_module(current["id"])
                if kind == "module"
                else client.retrieve_work_item(current["id"])
            )
            if kind == "module":
                drift = {
                    key: value
                    for key, value in changes.items()
                    if reread.get(key) != value
                }
            else:
                drift = _drift(reread, changes)
            if drift:
                raise WorkflowError(
                    f"legacy {kind} PATCH was not confirmed by re-read: {current['id']}"
                )

    return {
        "actions": actions,
        "applied": apply,
        "cancelled_phase_count": len(unfinished_phases) if mode == "superseded" else 0,
        "mode": mode,
        "preserved_done_phase_count": len(completed_phases),
        "successor": successor,
        "verified": apply or not actions,
        "work_package": f"work-package:{wp_id}",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    route = commands.add_parser("route", help="resolve repository-local Plane ownership")
    route.add_argument("--repo", type=Path, default=Path.cwd())
    validate = commands.add_parser("validate-plan", help="validate an offline Work Package plan")
    validate.add_argument("plan", type=Path)
    render = commands.add_parser("render-plan", help="render deterministic Plane objects and HTML")
    render.add_argument("plan", type=Path)
    render.add_argument("--external-source")
    ledger = commands.add_parser("render-ledger", help="render the ignored local Phase ledger")
    ledger.add_argument("plan", type=Path)
    ledger.add_argument("--phase", type=int, required=True)
    summary = commands.add_parser("phase-summary", help="summarize Plane task-list HTML")
    summary.add_argument("--html-file", type=Path, required=True)
    for name in ("inspect-project", "inspect-work-package", "sync-work-package", "reconcile-work-package-design", "verify-hierarchy", "phase-start", "phase-record-commit-review", "phase-record-history-rewrite", "phase-complete", "work-package-review-start", "close-work-package", "mark-legacy-work-package", "retire-empty-module", "migrate-work-package-repositories", "delete-unstarted-work-package"):
        command = commands.add_parser(name)
        command.add_argument("--repo", type=Path, default=Path.cwd())
        if name in {"inspect-work-package", "phase-start", "phase-record-commit-review", "phase-record-history-rewrite", "phase-complete", "work-package-review-start", "close-work-package", "mark-legacy-work-package", "migrate-work-package-repositories"}:
            command.add_argument("--wp-id", required=True)
        if name in {"sync-work-package", "reconcile-work-package-design", "verify-hierarchy", "delete-unstarted-work-package"}:
            command.add_argument("plan", type=Path)
        if name in {"sync-work-package", "reconcile-work-package-design", "phase-start", "phase-record-commit-review", "phase-record-history-rewrite", "phase-complete", "work-package-review-start", "close-work-package", "mark-legacy-work-package", "retire-empty-module", "migrate-work-package-repositories", "delete-unstarted-work-package"}:
            command.add_argument("--apply", action="store_true")
        if name in {"phase-start", "phase-record-commit-review", "phase-record-history-rewrite", "phase-complete"}:
            command.add_argument("--phase", type=int, required=True)
        if name == "phase-complete":
            command.add_argument("--html-file", type=Path, required=True)
        if name in {"phase-record-commit-review", "phase-record-history-rewrite", "work-package-review-start", "close-work-package"}:
            command.add_argument("--receipt", type=Path, required=True)
        if name in {"mark-legacy-work-package", "retire-empty-module"}:
            command.add_argument("--successor", required=True)
            command.add_argument("--reason", required=True)
        if name == "mark-legacy-work-package":
            command.add_argument("--mode", choices=("historical", "superseded"), required=True)
        if name == "retire-empty-module":
            command.add_argument("--module-id", required=True)
        if name == "migrate-work-package-repositories":
            command.add_argument("--repository", action="append", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "route":
            emit(resolve_route(args.repo))
            return 0
        if args.command == "validate-plan":
            errors = validate_plan(load_json(args.plan))
            emit({"valid": not errors, "errors": errors})
            return 0 if not errors else 2
        if args.command == "render-plan":
            emit(render_objects(load_json(args.plan), args.external_source))
            return 0
        if args.command == "render-ledger":
            print(render_ledger(load_json(args.plan), args.phase), end="")
            return 0
        if args.command == "phase-summary":
            emit(phase_summary(args.html_file.read_text(encoding="utf-8")))
            return 0
        route = resolve_route(args.repo)
        client = PlaneClient.from_route(route)
        if args.command == "inspect-project":
            emit(inspect_project(client, route))
        elif args.command == "inspect-work-package":
            emit(inspect_wp(client, route, args.wp_id))
        elif args.command == "sync-work-package":
            result = reconcile_work_package(client, route, load_json(args.plan), apply=args.apply)
            emit({"applied": args.apply, "actions": result.actions, "verified": args.apply})
        elif args.command == "reconcile-work-package-design":
            emit(
                reconcile_work_package_design(
                    client, route, load_json(args.plan), apply=args.apply
                )
            )
        elif args.command == "verify-hierarchy":
            emit(verify_hierarchy(client, route, load_json(args.plan)))
        elif args.command == "phase-start":
            project = client.project()
            assert_project(route, project)
            assert_active_project(project)
            states = client.states()
            state = resolve_state(states, "started")
            completed = resolve_state(states, "completed")
            all_items = client.work_items()
            work_package = find_work_package(all_items, route, args.wp_id)
            phase_candidates = [
                candidate
                for candidate in all_items
                if candidate.get("external_source") == route["external_source"]
                and str(candidate.get("external_id", "")).startswith(f"phase:{args.wp_id}:")
            ]
            detached = [
                candidate.get("external_id")
                for candidate in phase_candidates
                if object_id(candidate.get("parent")) != work_package["id"]
            ]
            if detached:
                raise WorkflowError(
                    "Phase hierarchy drift; these items are not direct WP children: "
                    + ", ".join(map(str, detached))
                )
            phase_items = [
                client.retrieve_work_item(candidate["id"])
                for candidate in phase_candidates
            ]
            item = validate_phase_start_sequence(
                phase_items, args.phase, completed["id"], state["id"]
            )
            action = {"work_item_id": item["id"], "state_id": state["id"], "state_name": state["name"]}
            if args.apply:
                client.request("PATCH", f"{client.project_prefix}/work-items/{item['id']}", data={"state": state["id"]})
                reread = client.retrieve_work_item(item["id"])
                if object_id(reread.get("state")) != state["id"]:
                    raise WorkflowError("Phase start PATCH was not confirmed by re-read")
            emit({"applied": args.apply, "action": action, "verified": args.apply})
        elif args.command == "phase-complete":
            project = client.project()
            assert_project(route, project)
            assert_active_project(project)
            final_html = args.html_file.read_text(encoding="utf-8")
            item = find_phase(client, route, args.wp_id, args.phase)
            summary = validate_phase_completion(item.get("description_html") or "", final_html)
            state = resolve_state(client.states(), "completed")
            action = {"work_item_id": item["id"], "state_id": state["id"], "checked": summary["checked"], "total": summary["total"]}
            if args.apply:
                client.request(
                    "PATCH",
                    f"{client.project_prefix}/work-items/{item['id']}",
                    data={"description_html": final_html, "state": state["id"]},
                )
                reread = client.retrieve_work_item(item["id"])
                reread_summary = validate_phase_completion(
                    item.get("description_html") or "", reread.get("description_html") or ""
                )
                if (
                    object_id(reread.get("state")) != state["id"]
                    or reread_summary["sections"].get("实际证据")
                    != summary["sections"].get("实际证据")
                ):
                    raise WorkflowError("Phase completion PATCH was not confirmed by re-read")
            emit({"applied": args.apply, "action": action, "verified": args.apply})
        elif args.command == "phase-record-commit-review":
            emit(
                record_phase_commit_review(
                    client,
                    route,
                    args.wp_id,
                    args.phase,
                    load_json(args.receipt),
                    apply=args.apply,
                )
            )
        elif args.command == "phase-record-history-rewrite":
            emit(
                record_phase_history_rewrite(
                    client,
                    route,
                    args.wp_id,
                    args.phase,
                    load_json(args.receipt),
                    apply=args.apply,
                )
            )
        elif args.command == "work-package-review-start":
            emit(
                start_work_package_review(
                    client,
                    route,
                    args.wp_id,
                    load_json(args.receipt),
                    apply=args.apply,
                )
            )
        elif args.command == "migrate-work-package-repositories":
            emit(
                migrate_legacy_work_package_repositories(
                    client,
                    route,
                    args.wp_id,
                    args.repository,
                    apply=args.apply,
                )
            )
        elif args.command == "close-work-package":
            emit(
                close_work_package(
                    client,
                    route,
                    args.wp_id,
                    load_json(args.receipt),
                    apply=args.apply,
                )
            )
        elif args.command == "mark-legacy-work-package":
            emit(
                mark_legacy_work_package(
                    client,
                    route,
                    args.wp_id,
                    mode=args.mode,
                    successor=args.successor,
                    reason=args.reason,
                    apply=args.apply,
                )
            )
        elif args.command == "retire-empty-module":
            emit(
                retire_empty_module(
                    client,
                    route,
                    args.module_id,
                    successor=args.successor,
                    reason=args.reason,
                    apply=args.apply,
                )
            )
        elif args.command == "delete-unstarted-work-package":
            emit(
                delete_unstarted_work_package(
                    client,
                    route,
                    load_json(args.plan),
                    apply=args.apply,
                )
            )
        return 0
    except (WorkflowError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
