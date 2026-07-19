import asyncio
import importlib
import sys
from pathlib import Path

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.syspath_prepend(str(SERVER_ROOT))
    models = importlib.import_module("app.models.mas_workflow_models")
    workflow = importlib.import_module("app.services.mas.tool_workflow")
    executor = importlib.import_module("app.services.mas.tool_executor")
    return models, workflow, executor


def test_model_read_call_becomes_an_immediately_executable_agent_decision(runtime):
    models, workflow, _executor = runtime

    decision = workflow.decision_from_model_message(
        {
            "content": None,
            "tool_calls": [
                {
                    "id": "call-progress-123",
                    "function": {
                        "name": "get_weekly_progress",
                        "arguments": '{"window":"5"}',
                    },
                }
            ],
        }
    )

    assert decision.kind == models.DecisionKind.REQUEST_TOOL
    assert decision.tool_request.tool_name == models.ToolName.GET_WEEKLY_PROGRESS
    assert decision.tool_request.arguments == {"window": "5"}
    assert decision.tool_request.requires_confirmation is False


def test_model_write_call_becomes_a_confirmation_gated_agent_decision(runtime):
    models, workflow, _executor = runtime

    decision = workflow.decision_from_model_message(
        {
            "content": "I can mark that goal complete. Would you like me to proceed?",
            "tool_calls": [
                {
                    "id": "call-complete-123",
                    "function": {
                        "name": "mark_goal_complete",
                        "arguments": '{"goal_index":1}',
                    },
                }
            ],
        }
    )

    assert decision.kind == models.DecisionKind.AWAIT_CONFIRMATION
    assert decision.message == "I can mark that goal complete. Would you like me to proceed?"
    assert decision.tool_request.requires_confirmation is True


@pytest.mark.parametrize(
    "message",
    [
        {"content": None, "tool_calls": []},
        {
            "content": None,
            "tool_calls": [
                {"function": {"name": "delete_everything", "arguments": "{}"}}
            ],
        },
        {
            "content": None,
            "tool_calls": [
                {"function": {"name": "get_weekly_progress", "arguments": "{"}}
            ],
        },
        {
            "content": None,
            "tool_calls": [
                {"function": {"name": "get_weekly_progress", "arguments": "{}"}},
                {"function": {"name": "get_weekly_progress", "arguments": "{}"}},
            ],
        },
    ],
)
def test_invalid_or_ambiguous_model_output_fails_closed(runtime, message):
    _models, workflow, _executor = runtime

    with pytest.raises(workflow.ModelDecisionError):
        workflow.decision_from_model_message(message)


def test_plain_model_message_remains_a_reply_decision(runtime):
    models, workflow, _executor = runtime

    decision = workflow.decision_from_model_message(
        {"content": "Your weekly progress is ready.", "tool_calls": None}
    )

    assert decision == models.AgentDecision(
        kind=models.DecisionKind.REPLY,
        message="Your weekly progress is ready.",
    )


def test_read_tool_executes_and_the_result_is_fed_back_to_the_agent(runtime):
    models, workflow, executor_module = runtime
    feedback_results = []

    async def read_progress(_arguments):
        return {"weekly_progress": {"completed": 2, "total": 3}}

    async def continue_agent(result):
        feedback_results.append(result)
        return "You completed two of three goals this week."

    decision = models.AgentDecision(
        kind=models.DecisionKind.REQUEST_TOOL,
        tool_request=models.ToolRequest(
            tool_name=models.ToolName.GET_WEEKLY_PROGRESS,
            arguments={},
        ),
    )
    executor = executor_module.MASToolExecutor(
        {models.ToolName.GET_WEEKLY_PROGRESS: read_progress}
    )

    outcome = asyncio.run(
        workflow.run_tool_decision(executor, decision, continue_agent=continue_agent)
    )

    assert outcome["status"] == "completed"
    assert outcome["message"] == "You completed two of three goals this week."
    assert feedback_results[0].status == models.ToolResultStatus.SUCCEEDED


def test_write_tool_pauses_then_executes_only_after_confirmation(runtime):
    models, workflow, executor_module = runtime
    executions = []

    async def mark_complete(arguments):
        executions.append(arguments)
        return {"ok": True, "changed": True}

    async def continue_agent(_result):
        return "The goal has been marked complete."

    decision = models.AgentDecision(
        kind=models.DecisionKind.AWAIT_CONFIRMATION,
        message="Would you like me to mark goal 2 complete?",
        tool_request=models.ToolRequest(
            tool_name=models.ToolName.MARK_GOAL_COMPLETE,
            arguments={"goal_index": 1},
            requires_confirmation=True,
        ),
    )
    executor = executor_module.MASToolExecutor(
        {models.ToolName.MARK_GOAL_COMPLETE: mark_complete}
    )

    paused = asyncio.run(
        workflow.run_tool_decision(executor, decision, continue_agent=continue_agent)
    )
    completed = asyncio.run(
        workflow.run_tool_decision(
            executor,
            decision,
            confirmed=True,
            continue_agent=continue_agent,
        )
    )

    assert paused == {
        "status": "awaiting_confirmation",
        "message": "Would you like me to mark goal 2 complete?",
        "tool_request": decision.tool_request.dict(),
    }
    assert executions == [{"goal_index": 1}]
    assert completed["status"] == "completed"
    assert completed["message"] == "The goal has been marked complete."


def test_gra_continuation_validates_the_agent_response(runtime):
    _models, workflow, _executor = runtime

    class Gateway:
        async def call_mas_service(self, service, endpoint, data):
            assert service == "gra"
            assert endpoint == "/receive_tool_result"
            assert data["patient_id"] == "patient-1"
            return {
                "status": "message processed",
                "assistant_message": "You completed two of three goals.",
                "persisted": True,
            }

    continuation = workflow.build_gra_continuation(
        Gateway(), "patient-1", turn_index=8
    )
    result = asyncio.run(
        continuation(
            runtime[0].ToolResult(
                tool_name=runtime[0].ToolName.GET_WEEKLY_PROGRESS,
                status=runtime[0].ToolResultStatus.SUCCEEDED,
                payload={"completed": 2, "total": 3},
            )
        )
    )

    assert result == "You completed two of three goals."


def test_graph_model_write_request_is_normalized_for_chat_confirmation(runtime):
    models, workflow, executor_module = runtime
    persisted_prompts = []

    async def unused_handler(_arguments):
        raise AssertionError("write tool must not execute before confirmation")

    async def persist_confirmation(message):
        persisted_prompts.append(message)

    executor = executor_module.MASToolExecutor(
        {models.ToolName.MARK_GOAL_COMPLETE: unused_handler}
    )
    result = asyncio.run(
        workflow.handle_graph_model_message(
            executor,
            {
                "content": "Would you like me to mark goal 2 complete?",
                "tool_calls": [
                    {
                        "function": {
                            "name": "mark_goal_complete",
                            "arguments": '{"goal_index":1}',
                        }
                    }
                ],
            },
            continue_agent=lambda _result: None,
            persist_confirmation=persist_confirmation,
        )
    )

    assert persisted_prompts == ["Would you like me to mark goal 2 complete?"]
    assert result["assistant_message"] == persisted_prompts[0]
    assert result["persisted"] is True
    assert result["tool_confirmation"]["tool_name"] == "mark_goal_complete"


def test_confirmed_execution_dto_accepts_only_a_valid_continuation_turn(runtime):
    models, _workflow, _executor = runtime
    mas_models = importlib.import_module("app.models.mas_models")
    dto = mas_models.ExecuteWorkflowToolDTO(
        tool_request=models.ToolRequest(
            tool_name=models.ToolName.MARK_GOAL_COMPLETE,
            arguments={"goal_index": 1},
            requires_confirmation=True,
        ),
        confirmed=True,
        turn_index=8,
    )
    assert dto.turn_index == 8

    with pytest.raises(Exception):
        mas_models.ExecuteWorkflowToolDTO(
            tool_request=dto.tool_request,
            confirmed=True,
            turn_index=True,
        )
