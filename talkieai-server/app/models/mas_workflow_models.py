"""Versioned HTTP and action-boundary contracts for the future MAS workflow."""
from enum import Enum
import math
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, root_validator, validator
from app.services.mas.workflow_json import ensure_json_object


IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$"
WORKFLOW_VERSION_PATTERN = r"^v[1-9][0-9]*$"
CONTRACT_VERSION = "v1"


class DecisionKind(str, Enum):
    REPLY = "reply"
    REQUEST_TOOL = "request_tool"
    AWAIT_CONFIRMATION = "await_confirmation"
    CLARIFY = "clarify"
    CLOSE = "close"


class ToolName(str, Enum):
    GET_WEEKLY_PROGRESS = "get_weekly_progress"
    MARK_GOAL_COMPLETE = "mark_goal_complete"
    RESCHEDULE_REVIEW = "reschedule_review"


class ToolResultStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowMessageRequest(BaseModel):
    """API request boundary for a new workflow message; not checkpoint state."""

    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    mas_session_id: str
    request_id: str
    workflow_version: str = CONTRACT_VERSION
    message: str

    @validator("mas_session_id", "request_id")
    def validate_identifier(cls, value: str) -> str:
        import re

        if not isinstance(value, str) or not re.fullmatch(IDENTIFIER_PATTERN, value):
            raise ValueError("must be a stable identifier")
        return value

    @validator("workflow_version")
    def validate_workflow_version(cls, value: str) -> str:
        import re

        if not isinstance(value, str) or not re.fullmatch(WORKFLOW_VERSION_PATTERN, value):
            raise ValueError("must be a version such as v1")
        return value

    @validator("message")
    def validate_message(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 4000:
            raise ValueError("must be a non-empty message of at most 4000 characters")
        return value


class ToolRequest(BaseModel):
    """A proposed tool call. This model does not execute a tool."""

    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    tool_name: ToolName
    arguments: Dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False

    @validator("arguments")
    def validate_arguments(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return ensure_json_object(value)

    @root_validator
    def require_confirmation_for_writes(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        write_tools = {ToolName.MARK_GOAL_COMPLETE, ToolName.RESCHEDULE_REVIEW}
        if (
            values.get("tool_name") in write_tools
            and values.get("requires_confirmation") is not True
        ):
            raise ValueError("write tools require confirmation")
        return values


class ToolResult(BaseModel):
    """Versioned result contract for a tool call after a future executor runs it."""

    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    tool_name: ToolName
    status: ToolResultStatus
    payload: Dict[str, Any] = Field(default_factory=dict)
    error_code: Optional[str] = None

    @validator("payload")
    def validate_payload(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return ensure_json_object(value)


class RetrievalResult(BaseModel):
    """Versioned retrieval boundary; retrieval is not connected in Batch 1."""

    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    retrieval_id: str
    source_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("retrieval_id", "source_id")
    def validate_retrieval_identifier(cls, value: str) -> str:
        return WorkflowMessageRequest.validate_identifier(value)

    @validator("score")
    def validate_score(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("score must be finite")
        return value

    @validator("metadata")
    def validate_metadata(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return ensure_json_object(value)


class AgentDecision(BaseModel):
    """A side-effect-free, versioned decision proposed by an agent."""

    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    kind: DecisionKind
    message: Optional[str] = None
    tool_request: Optional[ToolRequest] = None
    retrieval_results: List[RetrievalResult] = Field(default_factory=list)

    @root_validator
    def validate_decision_shape(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        kind = values.get("kind")
        message = values.get("message")
        tool_request = values.get("tool_request")

        if kind in {DecisionKind.REQUEST_TOOL, DecisionKind.AWAIT_CONFIRMATION}:
            if tool_request is None:
                raise ValueError("tool decisions require a tool_request")
        elif tool_request is not None:
            raise ValueError("only tool decisions may include a tool_request")

        if kind == DecisionKind.AWAIT_CONFIRMATION and not tool_request.requires_confirmation:
            raise ValueError("confirmation decisions require a confirmation-gated tool")

        write_tools = {ToolName.MARK_GOAL_COMPLETE, ToolName.RESCHEDULE_REVIEW}
        if (
            kind == DecisionKind.REQUEST_TOOL
            and tool_request is not None
            and tool_request.tool_name in write_tools
        ):
            raise ValueError("write tools must await confirmation")

        if kind in {DecisionKind.REPLY, DecisionKind.CLARIFY, DecisionKind.CLOSE} and not message:
            raise ValueError("message decisions require a message")
        return values
