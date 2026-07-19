"""Model-decision and confirmation workflow for MAS tool calls."""
import json
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional

from pydantic import ValidationError

from app.models.mas_workflow_models import (
    AgentDecision,
    DecisionKind,
    ToolName,
    ToolRequest,
    ToolResult,
)
from app.services.mas.tool_executor import MASToolExecutor, WRITE_TOOLS


class ModelDecisionError(ValueError):
    pass


AgentContinuation = Callable[[ToolResult], Awaitable[str]]
ConfirmationPersister = Callable[[str], Awaitable[None]]


def _model_field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def decision_from_model_message(message: Any) -> AgentDecision:
    """Convert one provider response message into the versioned decision model."""
    content = _model_field(message, "content")
    tool_calls = _model_field(message, "tool_calls") or []
    if not isinstance(tool_calls, (list, tuple)):
        raise ModelDecisionError("tool_calls must be a list")

    if not tool_calls:
        if type(content) is not str or not content.strip():
            raise ModelDecisionError("model response must contain a reply or one tool call")
        return AgentDecision(kind=DecisionKind.REPLY, message=content.strip())

    if len(tool_calls) != 1:
        raise ModelDecisionError("exactly one tool call is allowed per model response")

    function = _model_field(tool_calls[0], "function")
    name = _model_field(function, "name")
    raw_arguments = _model_field(function, "arguments")
    if type(name) is not str or type(raw_arguments) is not str:
        raise ModelDecisionError("tool call requires a function name and JSON arguments")

    try:
        arguments = json.loads(raw_arguments)
        if not isinstance(arguments, dict):
            raise ModelDecisionError("tool arguments must be a JSON object")
        tool_name = ToolName(name)
        requires_confirmation = tool_name in WRITE_TOOLS
        request = ToolRequest(
            tool_name=tool_name,
            arguments=arguments,
            requires_confirmation=requires_confirmation,
        )
        kind = (
            DecisionKind.AWAIT_CONFIRMATION
            if requires_confirmation
            else DecisionKind.REQUEST_TOOL
        )
        prompt = content.strip() if type(content) is str and content.strip() else None
        if requires_confirmation and prompt is None:
            prompt = f"Would you like me to run {tool_name.value}?"
        return AgentDecision(kind=kind, message=prompt, tool_request=request)
    except (json.JSONDecodeError, ValueError, ValidationError) as error:
        if isinstance(error, ModelDecisionError):
            raise
        raise ModelDecisionError("invalid model tool call") from error


async def run_tool_decision(
    executor: MASToolExecutor,
    decision: AgentDecision,
    *,
    confirmed: bool = False,
    continue_agent: Optional[AgentContinuation] = None,
) -> Dict[str, Any]:
    if decision.kind in {DecisionKind.REPLY, DecisionKind.CLARIFY, DecisionKind.CLOSE}:
        return {"status": "completed", "message": decision.message}

    if decision.kind == DecisionKind.AWAIT_CONFIRMATION and not confirmed:
        return {
            "status": "awaiting_confirmation",
            "message": decision.message,
            "tool_request": decision.tool_request.dict(),
        }

    if decision.kind not in {DecisionKind.REQUEST_TOOL, DecisionKind.AWAIT_CONFIRMATION}:
        raise ValueError("decision cannot enter the tool workflow")
    if decision.tool_request is None:
        raise ValueError("tool workflow requires a tool request")

    result = await executor.execute(decision.tool_request, confirmed=confirmed)
    if continue_agent is None:
        return {
            "status": "completed",
            "message": None,
            "tool_result": result.dict(),
        }
    message = await continue_agent(result)
    if type(message) is not str or not message.strip():
        raise ValueError("agent continuation must return a non-empty message")
    return {
        "status": "completed",
        "message": message.strip(),
        "tool_result": result.dict(),
    }


def build_gra_continuation(
    gateway: Any,
    patient_id: str,
    turn_index: int,
) -> AgentContinuation:
    async def continue_agent(result: ToolResult) -> str:
        response = await gateway.call_mas_service(
            "gra",
            "/receive_tool_result",
            data={
                "patient_id": patient_id,
                "turn_index": turn_index,
                "tool_result": result.dict(),
            },
        )
        if (
            not isinstance(response, dict)
            or response.get("persisted") is not True
            or type(response.get("assistant_message")) is not str
            or not response["assistant_message"].strip()
        ):
            raise RuntimeError("GRA returned an invalid tool continuation")
        return response["assistant_message"].strip()

    return continue_agent


async def handle_graph_model_message(
    executor: MASToolExecutor,
    model_message: Any,
    *,
    continue_agent: AgentContinuation,
    persist_confirmation: Optional[ConfirmationPersister] = None,
) -> Dict[str, Any]:
    decision = decision_from_model_message(model_message)
    outcome = await run_tool_decision(
        executor,
        decision,
        continue_agent=continue_agent,
    )
    if outcome["status"] == "awaiting_confirmation":
        if persist_confirmation is not None:
            await persist_confirmation(outcome["message"])
        return {
            "status": "message processed",
            "assistant_message": outcome["message"],
            "persisted": True,
            "tool_confirmation": outcome["tool_request"],
        }
    return {
        "status": "message processed",
        "assistant_message": outcome["message"],
        "persisted": True,
        "tool_result": outcome.get("tool_result"),
    }
