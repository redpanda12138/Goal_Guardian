import json

import pytest

from adaptive_agent import generate_stage_reply
from grounded_knowledge import json_call


SOURCE = {"source_id": "test-weekly-plan-01", "content": "Action plans specify when, where and how to act. Plans are reviewed weekly.", "metadata": {"title": "Planning"}}


def payload(question="How should I reconsider a plan that feels too difficult?"):
    return {"active_agent": "GRA", "stage_count": 5, "ranges": {"GRA": [5, 8, 10]},
            "chat_history": [{"id": "u1", "role": "user", "content": question}],
            "context": {"retrieval": [SOURCE]}}


def model_sequence(*outputs):
    calls = []
    def model(messages, temperature, tools):
        calls.append((messages, tools))
        item = outputs[min(len(calls) - 1, len(outputs) - 1)]
        return {"content": json.dumps(item)}
    return model, calls


def draft(source_id="test-weekly-plan-01", quote="Plans are reviewed weekly."):
    return {"answerable": True, "claims": [{"text": "Review the plan each week.", "source_id": source_id, "support_quote": quote}]}


def test_knowledge_answer_has_verified_citation_no_tool_and_no_completion():
    model, calls = model_sequence({"kind": "knowledge"}, draft(), {"supported": [True], "answers_question": True})
    result = generate_stage_reply("GRA", payload(), model, tools=[{"type": "function"}])
    assert result.get("turn_kind") == "knowledge"
    assert "[test-weekly-plan-01]" in result["assistant_message"]
    assert result["assessment"]["decision"] == "continue"
    assert not any(result["assessment"]["criteria"].values())
    assert result["grounding"]["status"] == "supported"
    assert all(not tools for _, tools in calls)


@pytest.mark.parametrize("bad", [draft("invented-source-01"), draft(quote="Review every Sunday evening.")])
def test_fabricated_source_or_quote_never_reaches_the_answer(bad):
    model, _ = model_sequence({"kind": "knowledge"}, bad)
    result = generate_stage_reply("GRA", payload(), model)
    assert result.get("grounding", {}).get("status") == "unverified"
    assert "invented-source" not in result["assistant_message"]
    assert "Sunday" not in result["assistant_message"]


def test_valid_quote_does_not_make_an_unsupported_claim_acceptable():
    bad = draft()
    bad["claims"][0]["text"] = "The paper proves GoalGuardian improves adherence by 90 percent."
    model, _ = model_sequence({"kind": "knowledge"}, bad, {"supported": [False], "answers_question": False})
    result = generate_stage_reply("GRA", payload(), model)
    assert result.get("grounding", {}).get("status") == "unverified"
    assert "90" not in result["assistant_message"]


def test_irrelevant_retrieval_can_yield_an_explicit_no_evidence_answer():
    model, calls = model_sequence({"kind": "knowledge"}, {"answerable": False, "claims": []})
    result = generate_stage_reply("GRA", payload("What clinical trial percentage did GoalGuardian achieve?"), model)
    assert result.get("grounding", {}).get("status") == "insufficient_evidence"
    assert "test-weekly-plan-01" not in result["assistant_message"]
    assert len(calls) == 2


def test_account_read_still_reaches_the_existing_tool_boundary():
    calls = []
    tool = {"content": None, "tool_calls": [{"function": {"name": "get_weekly_progress", "arguments": "{}"}}]}
    def model(messages, temperature, tools):
        calls.append(tools)
        return {"content": '{"kind":"account_read"}'} if len(calls) == 1 else tool
    tools = [{"type": "function", "function": {"name": "get_weekly_progress"}},
             {"type": "function", "function": {"name": "mark_goal_complete"}}]
    result = generate_stage_reply("GRA", payload("Show my saved completion totals."), model, tools)
    assert result.get("model_message") == tool
    assert len(calls) == 2
    assert [item["function"]["name"] for item in calls[1]] == ["get_weekly_progress"]


def test_unknown_turn_classification_fails_closed_without_tools():
    model, calls = model_sequence({"kind": "advance"})
    result = generate_stage_reply("GRA", payload(), model)
    assert result.get("turn_kind") == "knowledge"
    assert not any(result["assessment"]["criteria"].values())
    assert all(not tools for _, tools in calls)


def test_account_read_rejects_model_generated_write_even_if_schema_was_filtered():
    calls = []
    def model(messages, temperature, tools):
        calls.append(tools)
        if len(calls) == 1:
            return {"content": '{"kind":"account_read"}'}
        return {"content": None, "tool_calls": [{"function": {"name": "mark_goal_complete", "arguments": "{}"}}]}
    result = generate_stage_reply("GRA", payload("Show my saved totals."), model,
                                  [{"function": {"name": "get_weekly_progress"}}])
    assert "model_message" not in result


def test_grounding_receives_source_identity_and_conversation_context():
    data = payload("Which review was that?")
    data["chat_history"].insert(0, {"id": "a0", "role": "assistant", "content": "We discussed monitoring behaviour."})
    data["context"]["retrieval"][0] = {**SOURCE, "metadata": {"title": "Planning review", "authors": ["Author"], "year": 2020}}
    model, calls = model_sequence({"kind": "knowledge"}, draft(), {"supported": [True], "answers_question": True})
    generate_stage_reply("GRA", data, model)
    supplied = json.loads(calls[1][0][1]["content"])
    assert supplied["sources"][0]["title"] == "Planning review"
    assert supplied["history"][0]["id"] == "a0"


def test_mixed_review_keeps_personal_assessment_but_replaces_unverified_research_answer():
    assessment = {"decision": "continue", "criteria": {}, "evidence": {}, "reason": "Need next action."}
    model, _ = model_sequence({"kind": "mixed_review"},
        {"assistant_message": "Research proves this improves adherence by 90 percent.", "assessment": assessment},
        draft(), {"supported": [True], "answers_question": True})
    result = generate_stage_reply("GRA", payload("I walked twice. What does research suggest about weekly planning?"), model)
    assert result.get("turn_kind") == "mixed_review"
    assert result["assessment"] == assessment
    assert "90" not in result["assistant_message"]
    assert result["grounding"]["status"] == "supported"


def test_json_response_accepts_a_single_complete_markdown_envelope():
    model = lambda *args: {"content": '```json\n{"supported":[true],"answers_question":true}\n```'}
    assert json_call(model, "Check", {})["supported"] == [True]


def test_json_response_still_rejects_prose_or_multiple_objects():
    for text in ('Explanation: {"supported":[true]}', '{"a":1}{"b":2}', '```json\n{}\n``` trailing'):
        with pytest.raises(ValueError):
            json_call(lambda *args: {"content": text}, "Check", {})


def test_answer_rejects_extra_claims_instead_of_appending_related_studies():
    extra = draft()
    extra["claims"] *= 2
    model, _ = model_sequence({"kind": "knowledge"}, extra, {"supported": [True, True], "answers_question": True})
    result = generate_stage_reply("GRA", payload(), model)
    assert result["grounding"]["status"] == "unverified"


def test_overall_effect_is_not_relabelled_as_an_isolated_effect():
    isolated = draft()
    isolated["claims"][0]["text"] = "Action planning alone had no effect."
    model, _ = model_sequence({"kind": "knowledge"}, isolated, {"supported": [True], "answers_question": True})
    result = generate_stage_reply("GRA", payload(), model)
    assert result["grounding"]["status"] == "unverified"
    assert "alone" not in result["assistant_message"]
