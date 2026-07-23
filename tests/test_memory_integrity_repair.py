from diagnostics.memory_integrity_repair import (
    build_memory_repair_plan,
    classify_memory_finding,
    merge_memory_case,
)


def test_high_risk_active_chain_blocks_auto_apply():
    plan = build_memory_repair_plan(
        {
            "ok": False,
            "card_count": 2,
            "findings": [
                {"code": "active_supersedes_active", "severity": "high"},
                {"code": "missing_protocol_fields", "severity": "medium"},
            ],
        }
    )
    assert plan["blocked"] is True
    assert plan["safe_to_auto_apply"] is False
    assert "RX-MEM-003" in plan["prescription_ids"]
    assert "RX-MEM-004" in plan["prescription_ids"]


def test_capacity_finding_maps_to_rx_mem_001_without_confirmation():
    action = classify_memory_finding({"code": "memory_md_over_capacity", "severity": "high"})
    assert action.prescription_id == "RX-MEM-001"
    assert action.requires_confirmation is False
    assert action.risk == "low"


def test_merge_memory_case_keeps_codes_for_case_notes():
    merged = merge_memory_case(
        {"title": "memory drift"},
        {"ok": False, "findings": [{"code": "client_coverage_gap"}]},
        {"prescription_ids": ["RX-MEM-005"], "blocked": False},
    )
    assert merged["memory_integrity"]["finding_codes"] == ["client_coverage_gap"]
    assert merged["memory_integrity"]["prescription_ids"] == ["RX-MEM-005"]
