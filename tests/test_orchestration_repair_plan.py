from diagnostics.orchestration_repair_plan import repair_plan, requires_human_approval


def test_repair_plan_deduplicates_and_marks_unsafe_steps():
    steps = repair_plan(["stale_pending_event", "transition_drift", "stale_pending_event"])
    assert [s.action for s in steps] == ["claim_or_requeue_event", "regenerate_transition_table"]
    assert requires_human_approval(steps) is True


def test_unknown_issue_is_ignored():
    assert repair_plan(["unknown"] ) == []
