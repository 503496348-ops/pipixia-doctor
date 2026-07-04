from diagnostics.agent_sandbox_repair_context import build_repair_plan, classify_sandbox_finding, merge_runtime_context


def test_high_risk_writable_path_requires_confirmation_and_blocks():
    plan = build_repair_plan({"findings": [{"code": "overbroad_writable_path", "severity": "high"}]})
    assert plan["blocked"] is True
    assert plan["actions"][0]["requires_confirmation"] is True


def test_low_risk_network_toolset_mismatch_can_be_auto_planned():
    action = classify_sandbox_finding({"code": "network_without_web_toolset", "severity": "low"})
    assert action.risk == "low"
    assert action.requires_confirmation is False


def test_runtime_context_is_merged_into_case_record_without_secrets():
    merged = merge_runtime_context(
        {"title": "diagnosis"},
        {"sandbox": {"profile": "default", "workspace": "/tmp/work"}, "findings": [{"code": "workspace_not_absolute"}]},
    )
    assert merged["runtime_context"]["profile"] == "default"
    assert merged["runtime_context"]["finding_codes"] == ["workspace_not_absolute"]
