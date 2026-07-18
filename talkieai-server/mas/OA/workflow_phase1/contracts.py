import json
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional, TypedDict

AgentName = Literal["SOA", "GRA", "SCA", "SSA"]
EventType = Literal["user_turn", "agent_transition_intent", "scheduled_start"]
RouteStatus = Literal["ready", "completed", "error"]

class RequiredGraphState(TypedDict):
    patient_id: str
    session_generation: int
    workflow_version: str
    request_id: str
    event_type: EventType
    turn_index: int
    session_status: Literal["active", "completed"]

class GraphState(RequiredGraphState, total=False):
    requested_agent: AgentName
    selected_agent: AgentName
    route_reason: str
    route_status: RouteStatus
    error_category: str

@dataclass(frozen=True)
class RouteDecision:
    selected_agent: Optional[AgentName]
    route_reason: str
    route_status: RouteStatus

def validate_graph_input(raw: Mapping[str, Any]) -> GraphState:
    required = {"patient_id", "session_generation", "workflow_version", "request_id", "event_type", "turn_index", "session_status"}
    allowed = required | {"requested_agent"}
    if required - set(raw):
        raise ValueError("missing required graph field")
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unknown graph field: {sorted(unknown)[0]}")
    try:
        json.dumps(raw, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("graph input must contain JSON-compatible values") from error
    for field in ("patient_id", "workflow_version", "request_id", "event_type", "session_status"):
        if type(raw[field]) is not str or not raw[field]:
            raise ValueError(f"{field} must be a non-empty string")
    if type(raw["session_generation"]) is not int or raw["session_generation"] < 1:
        raise ValueError("session_generation must be a positive integer")
    if type(raw["turn_index"]) is not int or not 0 <= raw["turn_index"] <= 15:
        raise ValueError("turn_index must be between 0 and 15")
    if raw["workflow_version"] != "oa_graph_v1":
        raise ValueError("unsupported workflow_version")
    if raw["event_type"] not in {"user_turn", "agent_transition_intent", "scheduled_start"}:
        raise ValueError("unsupported event_type")
    if raw["session_status"] not in {"active", "completed"}:
        raise ValueError("unsupported session_status")
    requested = raw.get("requested_agent")
    if requested is not None and requested not in {"SOA", "GRA", "SCA", "SSA"}:
        raise ValueError("unsupported requested_agent")
    if raw["event_type"] == "agent_transition_intent" and requested is None:
        raise ValueError("requested_agent is required for transition intent")
    return dict(raw)  # type: ignore[return-value]

def decision_from_state(state: GraphState) -> RouteDecision:
    return RouteDecision(state.get("selected_agent"), state["route_reason"], state["route_status"])
