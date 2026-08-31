import pytest

from adaptive_workflow import AdaptiveWorkflow
from adaptive_policy import CRITERIA
from mas_memory_store import reset_engine_cache


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "workflow.db"))
    reset_engine_cache()
    workflow = AdaptiveWorkflow("test-patient")
    workflow.reset()
    yield workflow
    reset_engine_cache()


def reply(snapshot, ready=True):
    criteria = CRITERIA[snapshot["active_agent"]]
    return {
        "assistant_message": "Let us continue the review.",
        "assessment": {
            "decision": "advance" if ready else "clarify",
            "criteria": {key: ready for key in criteria},
            "evidence": {key: [snapshot["chat_history"][-1]["id"]] if ready else [] for key in criteria},
            "reason": "Required items are available." if ready else "More detail is needed.",
        },
    }


def turn(workflow, request_id, ready=True):
    snapshot = workflow.accept(request_id, "My review response", workflow.get()["session_generation"])
    return workflow.finish(request_id, snapshot["revision"], reply(snapshot, ready))


def test_duplicate_turn_replays_without_increment_or_second_handoff(workflow):
    turn(workflow, "r1")
    before = workflow.get()
    replay = workflow.accept("r1", "My review response", before["session_generation"])
    assert replay["requests"]["r1"]["response"] == before["requests"]["r1"]["response"]
    assert workflow.get()["stage_count"] == 1
    assert len(workflow.get()["chat_history"]) == 2


def test_conflicting_duplicate_and_concurrent_turn_are_rejected(workflow):
    workflow.accept("r1", "first", 1)
    with pytest.raises(ValueError, match="request_conflict"):
        workflow.accept("r1", "different", 1)
    with pytest.raises(ValueError, match="turn_in_progress"):
        workflow.accept("r2", "second", 1)


def test_early_handoff_resets_only_stage_count(workflow):
    for i in range(3):
        turn(workflow, str(i))
    state = workflow.get()
    assert state["active_agent"] == "GRA"
    assert state["stage_count"] == 0
    assert state["turn_index"] == 3
    assert len(state["chat_history"]) == 6


def test_stale_completion_cannot_write_after_reset(workflow):
    snapshot = workflow.accept("old", "response", 1)
    workflow.reset()
    with pytest.raises(ValueError, match="stale_state"):
        workflow.finish("old", snapshot["revision"], reply(snapshot))
    assert workflow.get()["chat_history"] == []


def test_upper_bound_pauses_after_one_extension_without_claiming_complete(workflow):
    for i in range(7):
        turn(workflow, str(i), ready=False)
    assert workflow.get()["recovery_requested"] is True
    workflow.control("extend", 1)
    turn(workflow, "extra1", ready=False)
    turn(workflow, "extra2", ready=False)
    assert workflow.get()["session_status"] == "paused"
    assert workflow.get()["active_agent"] == "SOA"
    restored = AdaptiveWorkflow("test-patient")
    restored.control("resume", 1)
    assert restored.get()["stage_count"] == 9
    assert restored.get()["session_status"] == "active"


def test_long_conversation_is_not_closed_at_turn_fifteen(workflow, monkeypatch):
    monkeypatch.setenv("OA_ADAPTIVE_SOA_RANGE", "3,5,25")
    workflow.reset()
    for i in range(16):
        turn(workflow, str(i), ready=False)
    assert workflow.get()["turn_index"] == 16
    assert workflow.get()["session_status"] == "active"


def test_tool_event_preserves_count_and_stop_waits_for_executing_write(workflow):
    for i in range(3):
        turn(workflow, "opening" + str(i))
    snapshot = workflow.accept("tool", "mark complete", 1)
    workflow.finish("tool", snapshot["revision"], {
        "model_message": {"content": None, "tool_calls": [{"function": {
            "name": "mark_goal_complete", "arguments": "{\"goal_index\": 0}"}}]},
    })
    workflow.tool_event("tool", "executing", 1)
    workflow.control("stop", 1)
    assert workflow.get()["session_status"] == "paused"
    workflow.tool_event("tool", "succeeded", 1, {"status": "succeeded"})
    assert workflow.get()["session_status"] == "completed"
    assert workflow.get()["review_outcome"] == "stopped"
    assert workflow.get()["stage_count"] == 1


def test_stop_cancels_unconfirmed_action_and_old_tool_event_is_rejected(workflow):
    for i in range(3):
        turn(workflow, "opening" + str(i))
    snapshot = workflow.accept("tool", "mark complete", 1)
    workflow.finish("tool", snapshot["revision"], {"model_message": {"tool_calls": [
        {"function": {"name": "mark_goal_complete", "arguments": "{\"goal_index\": 0}"}}
    ]}})
    workflow.control("stop", 1)
    assert workflow.get()["actions"]["tool"]["status"] == "cancelled"
    with pytest.raises(ValueError):
        workflow.tool_event("tool", "executing", 1)
    workflow.reset()
    with pytest.raises(ValueError, match="stale_session_generation"):
        workflow.tool_event("tool", "succeeded", 1)


def test_recovery_prompt_cannot_be_bypassed_by_more_ordinary_turns(workflow):
    for i in range(7):
        turn(workflow, str(i), ready=False)
    with pytest.raises(ValueError, match="recovery_choice_required"):
        workflow.accept("extra", "more detail", 1)


def test_skipped_outcome_survives_closing_acknowledgement(workflow):
    workflow.control("skip", 1)
    turn(workflow, "closing")
    assert workflow.get()["session_status"] == "completed"
    assert workflow.get()["review_outcome"] == "skipped"


@pytest.mark.parametrize("calls", ["bad", [{"function": {"name": "unknown", "arguments": "{}"}}],
    [{"function": {"name": "mark_goal_complete", "arguments": "{}"}}]])
def test_invalid_tools_never_reserve_an_action(workflow, calls):
    for i in range(3):
        turn(workflow, str(i))
    state = workflow.accept("invalid-tool", "request", 1)
    result = workflow.finish("invalid-tool", state["revision"], {"model_message": {"tool_calls": calls}})
    assert result["status"] == "ok"
    assert workflow.get()["actions"] == {}
    workflow.accept("next", "another response", 1)


def test_opening_cannot_request_tools_or_send_rejected_handoff(workflow):
    state = workflow.accept("early", "hello", 1)
    output = reply(state)
    output["assistant_message"] = "Goodbye! Your review is complete."
    output["model_message"] = {"tool_calls": [{"function": {"name": "get_weekly_progress", "arguments": "{}"}}]}
    result = workflow.finish("early", state["revision"], output)
    assert "Goodbye" not in result["assistant_message"]
    assert result["current_agent"] == "SOA"
    assert workflow.get()["actions"] == {}


def test_expired_dispatch_is_reclaimed_without_recounting_and_rejects_late_result(workflow):
    workflow.accept("request", "hello", 1)
    old = workflow.claim_dispatch("request", 1, now=100)
    with pytest.raises(ValueError, match="turn_in_progress"):
        workflow.claim_dispatch("request", 1, now=101)
    restored = AdaptiveWorkflow("test-patient")
    current = restored.claim_dispatch("request", 1, now=281)
    with pytest.raises(ValueError, match="stale_state"):
        workflow.finish("request", old["revision"], reply(old))
    restored.finish("request", current["revision"], reply(current))
    assert restored.get()["stage_count"] == 1


def test_full_early_and_late_handoffs_finish_with_content_not_global_count(workflow):
    for i in range(6):
        turn(workflow, "soa" + str(i), ready=i == 5)
    assert workflow.get()["active_agent"] == "GRA"  # Later than reference 5.
    for i in range(5):
        turn(workflow, "gra" + str(i))
    assert workflow.get()["active_agent"] == "SCA"  # Earlier than reference 8.
    turn(workflow, "sca")
    state = workflow.get()
    assert state["session_status"] == "completed"
    assert state["turn_index"] == 12
    assert state["summary_status"] == "pending"


def test_early_pause_resume_preserves_the_assessment_range(workflow):
    workflow.control("pause", 1)
    workflow.control("resume", 1)
    assert workflow.get()["ranges"]["SOA"] == [3, 5, 7]
    for i in range(3):
        turn(workflow, str(i))
    assert workflow.get()["active_agent"] == "GRA"


def test_progress_tool_renders_actual_totals_without_a_new_turn(workflow):
    for i in range(3):
        turn(workflow, str(i))
    state = workflow.accept("progress", "How many goals are completed?", 1)
    workflow.finish("progress", state["revision"], {"model_message": {"tool_calls": [
        {"function": {"name": "get_weekly_progress", "arguments": "{}"}}]}})
    state = workflow.tool_event("progress", "succeeded", 1, {"tool_name": "get_weekly_progress",
        "status": "succeeded", "payload": {"weekly_progress": {"completed": 2, "total": 3}}})
    assert state["chat_history"][-1]["content"] == "Your weekly progress shows 2 of 3 goals completed."
    assert state["stage_count"] == 1
