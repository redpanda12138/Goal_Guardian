"""Knowledge answers must not count as evidence that a goal review is complete."""

import pytest

from adaptive_policy import CRITERIA
from adaptive_workflow import AdaptiveWorkflow
from mas_memory_store import reset_engine_cache


ANSWER = "An action plan specifies when, where and how to act. [bailey_2019_plan]"


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "knowledge-turn.db"))
    for stage in ("SOA", "GRA", "SCA"):
        monkeypatch.delenv("OA_ADAPTIVE_" + stage + "_RANGE", raising=False)
    reset_engine_cache()
    instance = AdaptiveWorkflow("knowledge-turn-test-patient")
    instance.reset()

    def enter_review(state):
        state["active_agent"] = "GRA"
        return state

    instance.update(enter_review)
    yield instance
    reset_engine_cache()


def set_review_count(workflow, count):
    def update(state):
        state["stage_count"] = count
        return state

    workflow.update(update)


def assessment(reference, *, ready):
    return {
        "decision": "advance" if ready else "continue",
        "criteria": {key: ready for key in CRITERIA["GRA"]},
        "evidence": {key: [reference] if ready else [] for key in CRITERIA["GRA"]},
        "reason": "Review details are available." if ready else "This is a general knowledge question.",
    }


def finish_knowledge(workflow, request_id="knowledge", **extra):
    state = workflow.accept(request_id, "What does an action plan include?", 1)
    output = {
        "turn_kind": "knowledge",
        "assistant_message": ANSWER,
        "assessment": assessment(request_id, ready=False),
        **extra,
    }
    return workflow.finish(request_id, state["revision"], output)


def test_knowledge_answer_ignores_advance_without_consuming_review_count(workflow):
    set_review_count(workflow, 4)

    result = finish_knowledge(workflow, assessment=assessment("knowledge", ready=True))

    assert result["assistant_message"] == ANSWER
    assert result["current_agent"] == "GRA"
    assert result["stage_count"] == 4
    assert result["review_outcome"] == "in_progress"
    assert workflow.get()["summary_status"] == "not_requested"


@pytest.mark.parametrize("tool_name,arguments", [
    ("get_weekly_progress", "{}"),
    ("mark_goal_complete", '{"goal_index": 0}'),
])
def test_knowledge_answer_ignores_read_and_write_tools(workflow, tool_name, arguments):
    set_review_count(workflow, 4)

    result = finish_knowledge(workflow, model_message={"content": None, "tool_calls": [
        {"function": {"name": tool_name, "arguments": arguments}}
    ]})

    assert result["status"] == "ok"
    assert result["assistant_message"] == ANSWER
    assert result["current_agent"] == "GRA"
    assert result["stage_count"] == 4
    assert workflow.get()["actions"] == {}


def test_knowledge_turn_at_upper_boundary_does_not_trigger_recovery(workflow):
    set_review_count(workflow, 9)

    result = finish_knowledge(workflow)

    assert result["recovery_requested"] is False
    assert result["session_status"] == "active"
    assert result["stage_count"] == 9
    assert result["assistant_message"] == ANSWER
    # A second knowledge question must remain usable without a recovery choice.
    second = finish_knowledge(workflow, "knowledge-next")
    assert second["stage_count"] == 9
    assert second["recovery_requested"] is False


def test_knowledge_user_and_assistant_are_persisted_as_non_review_evidence(workflow):
    finish_knowledge(workflow)

    restored = AdaptiveWorkflow("knowledge-turn-test-patient")
    messages = restored.get()["chat_history"]
    assert [message["id"] for message in messages] == ["knowledge", "knowledge:reply"]
    assert messages[0]["role"] == "user"
    assert messages[1]["content"] == ANSWER
    assert all(message.get("review_evidence") is False for message in messages)


@pytest.mark.parametrize("knowledge_reference", ["knowledge", "knowledge:reply"])
def test_later_review_cannot_advance_using_knowledge_message_ids(workflow, knowledge_reference):
    finish_knowledge(workflow)
    set_review_count(workflow, 4)
    state = workflow.accept("review", "I have not described my progress yet.", 1)

    result = workflow.finish("review", state["revision"], {
        "assistant_message": "Your review is now complete.",
        "assessment": assessment(knowledge_reference, ready=True),
    })

    assert result["current_agent"] == "GRA"
    assert result["review_outcome"] == "in_progress"
    assert workflow.get()["summary_status"] == "not_requested"
    assert workflow.get()["decisions"][-1]["reason"] == "invalid_assessment"


def test_real_user_review_evidence_still_advances_after_knowledge_question(workflow):
    finish_knowledge(workflow)
    set_review_count(workflow, 4)
    state = workflow.accept("review", (
        "My goal was to walk after lunch four times. I walked three times. "
        "Rain stopped the fourth walk; next week I will walk indoors when it rains."
    ), 1)

    result = workflow.finish("review", state["revision"], {
        "assistant_message": "The review details are clear; let us recap your next step.",
        "assessment": assessment("review", ready=True),
    })

    assert result["current_agent"] == "SCA"
    assert result["stage_count"] == 0
    assert workflow.get()["decisions"][-1]["reason"] == "stage_ready"


def test_replayed_knowledge_request_does_not_change_count_or_duplicate_messages(workflow):
    set_review_count(workflow, 4)
    result = finish_knowledge(workflow)

    replay = workflow.accept("knowledge", "What does an action plan include?", 1)

    assert replay["requests"]["knowledge"]["response"] == result
    assert replay["stage_count"] == 4
    assert replay["turn_index"] == 1
    assert len(replay["chat_history"]) == 2


def test_new_request_id_cannot_reuse_a_knowledge_assistant_message_id(workflow):
    finish_knowledge(workflow, "knowledge")
    before = workflow.get()

    with pytest.raises(ValueError):
        workflow.accept("knowledge:reply", "I have not reviewed my goal yet.", 1)

    assert workflow.get() == before


def test_new_request_cannot_generate_a_reply_id_already_used_by_history(workflow):
    # This older user ID would collide with the assistant ID for a new "next" request.
    finish_knowledge(workflow, "next:reply")
    before = workflow.get()

    with pytest.raises(ValueError):
        workflow.accept("next", "I have not reviewed my goal yet.", 1)

    assert workflow.get() == before


@pytest.mark.parametrize("count,ready,workflow_prompt", [
    (0, True, "Before summarising"),
    (9, False, "Continue for two more responses, or pause?"),
])
def test_mixed_review_preserves_grounded_answer_alongside_workflow_prompt(
    workflow, count, ready, workflow_prompt
):
    set_review_count(workflow, count)
    state = workflow.accept("mixed", "I walked twice. What does an action plan include?", 1)
    grounding = {"status": "supported", "citations": [{
        "source_id": "bailey_2019_plan",
        "support_quote": "An action plan specifies when, where and how to act.",
    }]}

    result = workflow.finish("mixed", state["revision"], {
        "turn_kind": "mixed_review",
        "assistant_message": ANSWER,
        "grounding": grounding,
        "assessment": assessment("mixed", ready=ready),
    })

    assert ANSWER in result["assistant_message"]
    assert workflow_prompt in result["assistant_message"]
    assert result["grounding"] == grounding
    restored = AdaptiveWorkflow("knowledge-turn-test-patient").get()
    assert restored["chat_history"][-1]["content"] == result["assistant_message"]
    assert restored["chat_history"][-1]["review_evidence"] is False
    assert restored["chat_history"][-2].get("review_evidence") is not False
    assert restored["active_agent"] == "GRA"
    assert restored["stage_count"] == count + 1


@pytest.mark.parametrize("tool_suffix", [":tool-result", ":confirmation"])
def test_new_request_cannot_generate_a_tool_message_id_already_used_by_history(workflow, tool_suffix):
    finish_knowledge(workflow, "next" + tool_suffix)
    before = workflow.get()

    with pytest.raises(ValueError):
        workflow.accept("next", "Show my saved progress.", 1)

    assert workflow.get() == before
