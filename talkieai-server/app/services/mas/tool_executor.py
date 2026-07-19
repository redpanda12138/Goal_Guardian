"""Authenticated MAS tool-call execution boundary.

The executor is intentionally independent from model providers and HTTP routes.
Callers inject account-scoped handlers, while this module owns the allowlist,
argument validation, confirmation gate, and versioned result envelope.
"""
from datetime import datetime
import logging
from typing import Any, Awaitable, Callable, Dict, Mapping

from app.models.mas_workflow_models import (
    ToolName,
    ToolRequest,
    ToolResult,
    ToolResultStatus,
)


ToolHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]
WRITE_TOOLS = {ToolName.MARK_GOAL_COMPLETE, ToolName.RESCHEDULE_REVIEW}
logger = logging.getLogger(__name__)


class InvalidToolArguments(ValueError):
    pass


def _reject_unknown(arguments: Mapping[str, Any], allowed: set[str]) -> None:
    unknown = set(arguments) - allowed
    if unknown:
        raise InvalidToolArguments(f"unsupported argument: {sorted(unknown)[0]}")


def _validate_arguments(tool_name: ToolName, arguments: Mapping[str, Any]) -> Dict[str, Any]:
    if tool_name == ToolName.GET_WEEKLY_PROGRESS:
        _reject_unknown(arguments, {"window"})
        window = arguments.get("window", "5")
        if type(window) is not str or window not in {"5", "10", "all"}:
            raise InvalidToolArguments("window must be one of: 5, 10, all")
        return {"window": window} if "window" in arguments else {}

    if tool_name == ToolName.MARK_GOAL_COMPLETE:
        _reject_unknown(arguments, {"goal_index", "note"})
        goal_index = arguments.get("goal_index")
        if type(goal_index) is not int or goal_index < 0:
            raise InvalidToolArguments("goal_index must be a non-negative integer")
        validated: Dict[str, Any] = {"goal_index": goal_index}
        if "note" in arguments:
            note = arguments["note"]
            if type(note) is not str or not note.strip() or len(note) > 500:
                raise InvalidToolArguments("note must be a non-empty string of at most 500 characters")
            validated["note"] = note.strip()
        return validated

    if tool_name == ToolName.RESCHEDULE_REVIEW:
        _reject_unknown(arguments, {"date"})
        date = arguments.get("date")
        if type(date) is not str or not date:
            raise InvalidToolArguments("date must be an ISO 8601 timestamp")
        try:
            parsed = datetime.fromisoformat(date.replace("Z", "+00:00"))
        except ValueError as error:
            raise InvalidToolArguments("date must be an ISO 8601 timestamp") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise InvalidToolArguments("date must include a timezone offset")
        return {"date": date}

    raise InvalidToolArguments("tool is not allowlisted")


class MASToolExecutor:
    def __init__(self, handlers: Mapping[ToolName, ToolHandler]):
        self._handlers = dict(handlers)

    async def execute(self, request: ToolRequest, confirmed: bool = False) -> ToolResult:
        try:
            arguments = _validate_arguments(request.tool_name, request.arguments)
        except InvalidToolArguments as error:
            return ToolResult(
                tool_name=request.tool_name,
                status=ToolResultStatus.FAILED,
                payload={"reason": str(error)},
                error_code="invalid_arguments",
            )

        if request.tool_name in WRITE_TOOLS and not confirmed:
            return ToolResult(
                tool_name=request.tool_name,
                status=ToolResultStatus.SKIPPED,
                payload={"reason": "explicit user confirmation is required"},
                error_code="confirmation_required",
            )

        handler = self._handlers.get(request.tool_name)
        if handler is None:
            return ToolResult(
                tool_name=request.tool_name,
                status=ToolResultStatus.FAILED,
                payload={"reason": "tool handler is unavailable"},
                error_code="tool_unavailable",
            )

        try:
            payload = await handler(arguments)
            if not isinstance(payload, dict):
                raise TypeError("tool handler must return a JSON object")
            if payload.get("ok") is False:
                return ToolResult(
                    tool_name=request.tool_name,
                    status=ToolResultStatus.FAILED,
                    payload=payload,
                    error_code="tool_rejected",
                )
            return ToolResult(
                tool_name=request.tool_name,
                status=ToolResultStatus.SUCCEEDED,
                payload=payload,
            )
        except Exception:
            logger.exception("MAS tool execution failed for %s", request.tool_name.value)
            return ToolResult(
                tool_name=request.tool_name,
                status=ToolResultStatus.FAILED,
                payload={"reason": "tool execution failed"},
                error_code="tool_execution_failed",
            )
