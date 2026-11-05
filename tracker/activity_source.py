"""Generic timelog source.

The dashboard asks this module for a day's timelog. Today the source is an MCP
server started over stdio (the Cursor timelog MCP). Another server can be
connected later by changing ACTIVITY_MCP_COMMAND / ACTIVITY_MCP_TOOL, as long
as its tool returns a project list with tasks or activities.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import shlex
from datetime import date
from typing import Any

from .config import (
    ACTIVITY_MCP_ARGS,
    ACTIVITY_MCP_COMMAND,
    ACTIVITY_MCP_CWD,
    ACTIVITY_MCP_PYTHONPATH,
    ACTIVITY_MCP_TOOL,
)

CATEGORY_LEAD = {
    "Testing & Verification": "Verified",
    "Debugging & Fixes": "Investigated",
    "Development": "Worked on",
    "Documentation": "Documented",
    "Research & Analysis": "Researched",
    "General": "Worked on",
}
CHATTY = re.compile(
    r"^(yes|no|nope|mostly|ok|okay|sure|thanks|let me|i['’]?ll|i will|i am|i['’]m)\b",
    re.I,
)


class ActivitySourceError(RuntimeError):
    """The configured activity source could not return a timelog."""


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text.replace(" ,", ",").strip(" -")


def _title_phrase(title: str) -> str:
    title = _clean(title).rstrip(".")
    if not title:
        return "the recorded work"
    if title[0].isupper() and not title.isupper():
        title = title[0].lower() + title[1:]
    return title


def _statement(text: str) -> str:
    """Turn a chat reply into a standalone sentence, dropping a leading 'I'."""
    text = re.sub(r"^I['’]ll\s+", "", text.strip())
    text = re.sub(r"^I(?:\s+am|'m)\s+", "", text)
    text = re.sub(r"^I\s+", "", text)
    if text:
        text = text[0].upper() + text[1:]
    if text and text[-1] not in ".!?":
        text += "."
    return text


def _best_statement(outcomes: list[str]) -> str:
    """Earliest complete finding. Later replies are often follow-ups that assume context."""
    for text in outcomes:
        chosen = []
        for part in re.split(r"(?<=[.!?])\s+", _clean(text)):
            part = part.strip()
            if len(part) < 45 or CHATTY.match(part) or "…" in part or "..." in part:
                continue
            chosen.append(_statement(part))
            if len(chosen) == 2:
                break
        if chosen:
            return " ".join(chosen)
    return ""


def describe_task(task: dict[str, Any]) -> str:
    """One grammatical description from the task's own title, requests and outcome."""
    source = task.get("source") or ""
    outcomes = [_clean(item) for item in task.get("outcomes") or [] if _clean(item)]
    if source == "git_commits" and outcomes:
        shown = [item.rstrip(".") for item in outcomes[:4]]
        extra = len(outcomes) - len(shown)
        text = "Committed changes: " + "; ".join(shown)
        if extra > 0:
            text += f"; and {extra} more"
        return text + "."
    files = [name for name in (task.get("files_changed") or []) if name]
    if source == "file_changes":
        if not files:
            return "Edited project files directly in the editor."
        shown = ", ".join(files[:5])
        suffix = f", and {len(files) - 5} more" if len(files) > 5 else ""
        return f"Edited project files directly in the editor, including {shown}{suffix}."
    statement = _best_statement(outcomes)
    if statement:
        return statement
    lead = CATEGORY_LEAD.get(task.get("category") or "", "Worked on")
    opening = f"{lead} {_title_phrase(task.get('task') or 'the recorded work')}."
    requests = [_clean(item) for item in task.get("user_requests") or [] if _clean(item)]
    if requests:
        return f"{opening} {_statement(requests[0])}"
    if files:
        return f"{opening} Updated {', '.join(files[:4])}."
    return opening


def hours_label(hours: float | None, duration: str | None) -> str:
    if hours is None:
        return "To be confirmed"
    label = f"{hours:.2f} h"
    if duration:
        label += f" ({duration})"
    return label


def _task_rows(project_name: str, raw_tasks: list[Any]) -> list[dict[str, Any]]:
    rows = []
    for task in raw_tasks:
        if isinstance(task, str):
            task = {"task": task, "description": task}
        if not isinstance(task, dict):
            continue
        if task.get("minutes") == 0 and not (task.get("description") or task.get("user_requests")):
            continue
        hours = task.get("hours")
        if isinstance(hours, str):
            try:
                hours = float(hours)
            except ValueError:
                hours = None
        duration = task.get("duration") if isinstance(task.get("duration"), str) else None
        description = _clean(task.get("description") or "") or describe_task(task)
        rows.append({
            "project": project_name,
            "description": description,
            "time": _clean(task.get("time") or ""),
            "hours": hours,
            "duration": duration,
            "hours_label": hours_label(hours if isinstance(hours, (int, float)) else None, duration),
            "category": _clean(task.get("category") or ""),
        })
    return rows


def normalize_report(payload: dict[str, Any], requested_day: str, source_name: str) -> dict[str, Any]:
    """Turn one MCP tool result into the shape the dashboard renders and exports."""
    projects = []
    for item in payload.get("projects") or []:
        if not isinstance(item, dict):
            continue
        name = _clean(item.get("project") or item.get("name") or "General") or "General"
        raw = item.get("tasks")
        if not raw and isinstance(item.get("activities"), list):
            raw = [{"task": text, "description": text} for text in item["activities"] if isinstance(text, str)]
        rows = _task_rows(name, raw or [])
        if not rows:
            continue
        measured = [row["hours"] for row in rows if isinstance(row["hours"], (int, float))]
        projects.append({
            "project": name,
            "tasks": rows,
            "total_hours": round(sum(measured), 2) if measured else None,
            "total_label": hours_label(round(sum(measured), 2), None) if measured else "To be confirmed",
        })
    measured_projects = [item["total_hours"] for item in projects if item["total_hours"] is not None]
    total = round(sum(measured_projects), 2) if measured_projects else None
    unconfirmed = sum(1 for item in projects for row in item["tasks"] if row["hours"] is None)
    weekday = ""
    try:
        weekday = date.fromisoformat(str(payload.get("date") or requested_day)).strftime("%A")
    except ValueError:
        pass
    return {
        "date": str(payload.get("date") or requested_day),
        "weekday": payload.get("weekday") or weekday,
        "timezone": payload.get("timezone") or "",
        "source": source_name,
        "projects": projects,
        "project_names": [item["project"] for item in projects],
        "task_count": sum(len(item["tasks"]) for item in projects),
        "total_hours": total,
        "total_label": hours_label(total, None) if total is not None else "To be confirmed",
        "unconfirmed": unconfirmed,
        "coverage_note": _clean(payload.get("coverage_note") or ""),
        "empty": not projects,
    }


def filter_report(report: dict[str, Any], project: str) -> dict[str, Any]:
    project = project.strip().lower()
    if not project:
        return report
    chosen = [item for item in report["projects"] if item["project"].lower() == project]
    measured = [item["total_hours"] for item in chosen if item["total_hours"] is not None]
    total = round(sum(measured), 2) if measured else None
    updated = dict(report)
    updated.update({
        "projects": chosen,
        "task_count": sum(len(item["tasks"]) for item in chosen),
        "total_hours": total,
        "total_label": hours_label(total, None) if total is not None else "To be confirmed",
        "unconfirmed": sum(1 for item in chosen for row in item["tasks"] if row["hours"] is None),
        "empty": not chosen,
        "project_filter": project,
    })
    return updated


def report_plaintext(report: dict[str, Any]) -> str:
    title_day = report.get("weekday") or ""
    heading = f"Timelog for {title_day + ', ' if title_day else ''}{report.get('date', '')}".strip()
    lines = [heading, ""]
    if report.get("empty"):
        lines.append("No activity was recorded for this date.")
    for project in report.get("projects") or []:
        lines.append(f"Project: {project['project']}")
        for task in project["tasks"]:
            when = task["time"] or "Time not recorded"
            lines.append(f"{when} — {task['hours_label']}")
            lines.append(task["description"])
            lines.append("")
        lines.append("")
    if not report.get("empty"):
        lines.append(f"Total: {report.get('total_label')} (approximate)")
    note = report.get("coverage_note")
    if note:
        lines += ["", note]
    return "\n".join(lines).strip() + "\n"


def report_csv(report: dict[str, Any]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Date", "Project", "Activity Description", "Time", "Duration", "Hours", "Category"])
    for project in report.get("projects") or []:
        for task in project["tasks"]:
            writer.writerow([
                report.get("date", ""),
                project["project"],
                task["description"],
                task["time"],
                task["duration"] or "",
                "" if task["hours"] is None else task["hours"],
                task["category"],
            ])
    return out.getvalue()


def _payload_from_result(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and structured:
        return structured
    texts = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            texts.append(text)
    raw = "\n".join(texts).strip()
    if not raw:
        raise ActivitySourceError("The activity source returned an empty response.")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ActivitySourceError("The activity source did not return a timelog.") from exc
    if not isinstance(parsed, dict):
        raise ActivitySourceError("The activity source did not return a timelog.")
    return parsed


async def fetch_report(day: str, project: str = "") -> dict[str, Any]:
    """Call the configured MCP tool and return a normalized timelog for one date."""
    command = (ACTIVITY_MCP_COMMAND or "").strip()
    if not command:
        raise ActivitySourceError(
            "No activity source is configured. Set ACTIVITY_MCP_COMMAND to the MCP server command."
        )
    try:
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client
    except ImportError as exc:
        raise ActivitySourceError("The MCP client is not installed in this application.") from exc

    env = dict(os.environ)
    if ACTIVITY_MCP_PYTHONPATH:
        env["PYTHONPATH"] = ACTIVITY_MCP_PYTHONPATH + os.pathsep + env.get("PYTHONPATH", "")
    params = StdioServerParameters(
        command=command,
        args=shlex.split(ACTIVITY_MCP_ARGS or ""),
        env=env,
        cwd=ACTIVITY_MCP_CWD or None,
    )
    tool = (ACTIVITY_MCP_TOOL or "generate_timelog").strip()
    arguments = {"target_date": day, "project": "", "manual_hours": ""}
    if tool == "get_timelog":
        arguments = {"request": f"timelog for {day}"}
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                available = {item.name for item in (await session.list_tools()).tools}
                if tool not in available:
                    if "generate_timelog" in available:
                        tool = "generate_timelog"
                    elif "get_timelog" in available:
                        tool, arguments = "get_timelog", {"request": f"timelog for {day}"}
                    else:
                        raise ActivitySourceError(
                            "The connected MCP server has no generate_timelog or get_timelog tool."
                        )
                result = await session.call_tool(tool, arguments)
    except ActivitySourceError:
        raise
    except FileNotFoundError as exc:
        raise ActivitySourceError(f"Activity source command was not found: {command}") from exc
    except Exception as exc:
        raise ActivitySourceError(f"Could not reach the activity source: {exc}") from exc
    if getattr(result, "isError", False):
        texts = " ".join(getattr(block, "text", "") for block in (result.content or []))
        raise ActivitySourceError(_clean(texts) or "The activity source reported an error.")
    report = normalize_report(_payload_from_result(result), day, tool)
    report["plain_text"] = report_plaintext(report if not project else filter_report(report, project))
    if project:
        filtered = filter_report(report, project)
        filtered["plain_text"] = report_plaintext(filtered)
        filtered["project_names"] = report["project_names"]
        return filtered
    return report
