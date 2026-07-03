"""Repair planning for generic orchestration runtimes."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepairStep:
    action: str
    reason: str
    safe_by_default: bool = True


REPAIR_MAP = {
    "transition_drift": RepairStep("regenerate_transition_table", "source and runtime transition tables disagree", False),
    "stale_pending_event": RepairStep("claim_or_requeue_event", "pending event exceeded idle threshold"),
    "repeated_delivery": RepairStep("quarantine_event", "event repeatedly redelivered and may be poison"),
    "missing_flow_log": RepairStep("rebuild_flow_log_from_audit", "flow log missing for active item"),
    "missing_confirmation_payload": RepairStep("return_to_verification", "confirmation state lacks requested transition"),
}


def repair_plan(issue_codes: list[str]) -> list[RepairStep]:
    seen: set[str] = set()
    steps: list[RepairStep] = []
    for code in issue_codes:
        if code in seen:
            continue
        seen.add(code)
        step = REPAIR_MAP.get(code)
        if step:
            steps.append(step)
    return steps


def requires_human_approval(steps: list[RepairStep]) -> bool:
    return any(not step.safe_by_default for step in steps)
