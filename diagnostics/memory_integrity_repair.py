"""Repair planner for memory integrity findings (PipiXia Doctor).

Consumes finding payloads from Hermes Doctor memory integrity diagnostics
and maps them to safe, reviewable RX-MEM prescriptions. Never executes repairs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class MemoryRepairAction:
    code: str
    prescription_id: str
    risk: str
    summary: str
    requires_confirmation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_FINDING_MAP: dict[str, MemoryRepairAction] = {
    "memory_md_over_capacity": MemoryRepairAction(
        code="memory_md_over_capacity",
        prescription_id="RX-MEM-001",
        risk="low",
        summary="Distill MEMORY.md: move durable facts to cards, drop task logs, keep hot layer under limit.",
        requires_confirmation=False,
    ),
    "memory_md_near_capacity": MemoryRepairAction(
        code="memory_md_near_capacity",
        prescription_id="RX-MEM-001",
        risk="low",
        summary="Proactively distill MEMORY.md before it blocks injection.",
        requires_confirmation=False,
    ),
    "card_directory_bloat": MemoryRepairAction(
        code="card_directory_bloat",
        prescription_id="RX-MEM-001",
        risk="medium",
        summary="Archive or merge stale memory cards; keep active set small.",
        requires_confirmation=True,
    ),
    "superseded_still_hot": MemoryRepairAction(
        code="superseded_still_hot",
        prescription_id="RX-MEM-003",
        risk="medium",
        summary="Remove superseded/expired lines from hot MEMORY.md; keep only active facts.",
        requires_confirmation=False,
    ),
    "active_supersedes_active": MemoryRepairAction(
        code="active_supersedes_active",
        prescription_id="RX-MEM-003",
        risk="high",
        summary="Mark the older card status=superseded and set superseded_by to the winner id.",
        requires_confirmation=True,
    ),
    "supersession_inverted": MemoryRepairAction(
        code="supersession_inverted",
        prescription_id="RX-MEM-003",
        risk="high",
        summary="Invert or repair supersession lineage so only the active winner remains hot.",
        requires_confirmation=True,
    ),
    "dangling_supersedes": MemoryRepairAction(
        code="dangling_supersedes",
        prescription_id="RX-MEM-003",
        risk="medium",
        summary="Drop dangling supersedes references or restore the missing card id.",
        requires_confirmation=False,
    ),
    "missing_protocol_fields": MemoryRepairAction(
        code="missing_protocol_fields",
        prescription_id="RX-MEM-004",
        risk="low",
        summary="Backfill clients/status/supersedes/cognitive_type on the memory card frontmatter.",
        requires_confirmation=False,
    ),
    "empty_clients": MemoryRepairAction(
        code="empty_clients",
        prescription_id="RX-MEM-004",
        risk="low",
        summary="Tag owning clients (hermes/codex/claude/...) on the card.",
        requires_confirmation=False,
    ),
    "unknown_status": MemoryRepairAction(
        code="unknown_status",
        prescription_id="RX-MEM-004",
        risk="low",
        summary="Normalize status to active|superseded|archived.",
        requires_confirmation=False,
    ),
    "client_coverage_gap": MemoryRepairAction(
        code="client_coverage_gap",
        prescription_id="RX-MEM-005",
        risk="medium",
        summary="Ensure each expected client is represented on at least one active card, or document intentional single-client scope.",
        requires_confirmation=True,
    ),
}


def classify_memory_finding(finding: Mapping[str, Any]) -> MemoryRepairAction:
    code = str(finding.get("code") or "unknown")
    if code in _FINDING_MAP:
        return _FINDING_MAP[code]
    hint = str(finding.get("prescription_hint") or "RX-MEM-001")
    return MemoryRepairAction(
        code=code,
        prescription_id=hint,
        risk=str(finding.get("severity") or "medium"),
        summary="Route memory finding to manual review with matching RX-MEM prescription.",
        requires_confirmation=True,
    )


def build_memory_repair_plan(integrity_payload: Mapping[str, Any]) -> dict[str, Any]:
    findings: Sequence[Mapping[str, Any]] = list(integrity_payload.get("findings") or [])
    actions = [classify_memory_finding(item).to_dict() for item in findings]
    blocked = any(a["risk"] == "high" for a in actions)
    auto = bool(actions) and all(
        (not a["requires_confirmation"]) and a["risk"] in {"low", "medium"} for a in actions
    )
    rx_ids = sorted({a["prescription_id"] for a in actions})
    return {
        "safe_to_auto_apply": auto and not blocked,
        "blocked": blocked,
        "actions": actions,
        "prescription_ids": rx_ids,
        "source_ok": bool(integrity_payload.get("ok", False)),
        "card_count": integrity_payload.get("card_count"),
    }


def merge_memory_case(case_record: Mapping[str, Any], integrity_payload: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(case_record)
    merged["memory_integrity"] = {
        "ok": integrity_payload.get("ok"),
        "finding_codes": [f.get("code") for f in integrity_payload.get("findings") or []],
        "prescription_ids": list(plan.get("prescription_ids") or []),
        "blocked": plan.get("blocked"),
    }
    return merged
