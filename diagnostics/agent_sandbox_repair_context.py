"""Repair-oriented sandbox context planner.

This module turns runtime context findings into safe, reviewable repair actions.
It never executes repairs; callers can present the plan for confirmation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Any


@dataclass(frozen=True)
class RepairAction:
    code: str
    risk: str
    summary: str
    requires_confirmation: bool = True


def classify_sandbox_finding(finding: Mapping[str, str]) -> RepairAction:
    code = finding.get("code", "unknown")
    if code == "overbroad_writable_path":
        return RepairAction(code, "high", "Restrict writable paths to a task-specific workspace.")
    if code == "workspace_not_absolute":
        return RepairAction(code, "medium", "Rewrite workspace configuration to an absolute path.", False)
    if code == "network_without_web_toolset":
        return RepairAction(code, "low", "Either disable network mode or explicitly enable the web toolset.", False)
    return RepairAction(code, "medium", "Route finding to manual review.")


def build_repair_plan(sandbox_payload: Mapping[str, Any]) -> dict[str, Any]:
    findings = list(sandbox_payload.get("findings") or [])
    actions = [classify_sandbox_finding(finding).__dict__ for finding in findings]
    return {
        "safe_to_auto_apply": actions and all(not action["requires_confirmation"] and action["risk"] in {"low", "medium"} for action in actions),
        "actions": actions,
        "blocked": any(action["risk"] == "high" for action in actions),
    }


def merge_runtime_context(case_record: Mapping[str, Any], sandbox_payload: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(case_record)
    merged["runtime_context"] = {
        "profile": (sandbox_payload.get("sandbox") or {}).get("profile"),
        "workspace": (sandbox_payload.get("sandbox") or {}).get("workspace"),
        "finding_codes": [item.get("code") for item in sandbox_payload.get("findings") or []],
    }
    return merged
