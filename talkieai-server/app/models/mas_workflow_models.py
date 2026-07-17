"""Versioned HTTP and action-boundary contracts for the future MAS workflow."""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, root_validator, validator


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

    contract_version: str = CONTRACT_VERSION
    tool_name: ToolName
    arguments: Dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False

    @validator("requires_confirmation")
    def require_confirmation_for_writes(cls, value: bool, values: Dict[str, Any]) -> bool:
        write_tools = {ToolName.MARK_GOAL_COMPLETE, ToolName.RESCHEDULE_REVIEW}
        if values.get("tool_name") in write_tools and value is not True:
            raise ValueError("write tools require confirmation")
        return value


class ToolResult(BaseModel):
    """Versioned result contract for a tool call after a future executor runs it."""

    contract_version: str = CONTRACT_VERSION
    tool_name: ToolName
    status: ToolResultStatus
    payload: Dict[str, Any] = Field(default_factory=dict)
    error_code: Optional[str] = None


class RetrievalResult(BaseModel):
    """Versioned retrieval boundary; retrieval is not connected in Batch 1."""

    contract_version: str = CONTRACT_VERSION
    retrieval_id: str
    source_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("retrieval_id", "source_id")
    def validate_retrieval_identifier(cls, value: str) -> str:
        return WorkflowMessageRequest.validate_identifier(value)


class AgentDecision(BaseModel):
    """A side-effect-free, versioned decision proposed by an agent."""

    contract_version: str = CONTRACT_VERSION
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

        if kind in {DecisionKind.REPLY, DecisionKind.CLARIFY, DecisionKind.CLOSE} and not message:
            raise ValueError("message decisions require a message")
        return values
