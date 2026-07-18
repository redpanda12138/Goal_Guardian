from typing import Any, Mapping
from langgraph.graph import END, StateGraph
from .contracts import GraphState, RouteDecision, decision_from_state, validate_graph_input
from .parity import decide_legacy_parity

def validate_event(state: GraphState) -> GraphState:
    try:
        return validate_graph_input(state)
    except ValueError as error:
        return {**state, "route_status": "error", "route_reason": "invalid_event", "error_category": str(error)}  # type: ignore[typeddict-item]

def after_validation(state: GraphState) -> str:
    return "invalid" if state.get("route_status") == "error" else "valid"

def classify_session(state: GraphState) -> GraphState:
    if state["turn_index"] == 15 or state["session_status"] == "completed":
        return {**state, "route_status": "completed", "route_reason": "session_completed"}
    return state

def select_route(state: GraphState) -> GraphState:
    decision = decide_legacy_parity(state)
    return {**state, "selected_agent": decision.selected_agent, "route_reason": decision.route_reason, "route_status": decision.route_status}  # type: ignore[typeddict-item]

def emit_completed(state: GraphState) -> GraphState:
    result = dict(state); result.pop("selected_agent", None)
    return {**result, "route_reason": "session_completed", "route_status": "completed"}  # type: ignore[return-value]

def after_classification(state: GraphState) -> str:
    if state.get("route_status") == "completed": return "completed"
    return "transition" if state["event_type"] == "agent_transition_intent" else "active"

def validate_transition_intent(state: GraphState) -> GraphState:
    expected = decide_legacy_parity(state)
    if state.get("requested_agent") != expected.selected_agent:
        return {**state, "route_status": "error", "route_reason": "transition_conflict"}
    return {**state, "selected_agent": expected.selected_agent, "route_status": "ready", "route_reason": "transition_approved"}  # type: ignore[typeddict-item]

def emit_route_error(state: GraphState) -> GraphState:
    result = dict(state); result.pop("selected_agent", None)
    return {**result, "route_status": "error", "route_reason": state.get("route_reason", "invalid_event")}  # type: ignore[return-value]

def build_phase1_graph():
    builder = StateGraph(GraphState)
    builder.add_node("validate_event", validate_event)
    builder.add_node("classify_session", classify_session)
    builder.add_node("select_legacy_parity_route", select_route)
    builder.add_node("validate_transition_intent", validate_transition_intent)
    builder.add_node("emit_completed", emit_completed)
    builder.add_node("emit_route_error", emit_route_error)
    builder.set_entry_point("validate_event")
    builder.add_conditional_edges("validate_event", after_validation, {"invalid": "emit_route_error", "valid": "classify_session"})
    builder.add_conditional_edges("classify_session", after_classification, {"completed": "emit_completed", "active": "select_legacy_parity_route", "transition": "validate_transition_intent"})
    builder.add_edge("emit_completed", END)
    builder.add_edge("emit_route_error", END)
    builder.add_edge("select_legacy_parity_route", END)
    builder.add_conditional_edges("validate_transition_intent", lambda state: "error" if state["route_status"] == "error" else "ready", {"error": "emit_route_error", "ready": END})
    return builder.compile(checkpointer=None)

def invoke_phase1_graph(raw: Mapping[str, Any]) -> RouteDecision:
    validated = validate_graph_input(raw)
    graph = build_phase1_graph()
    assert graph.checkpointer is None
    return decision_from_state(graph.invoke(validated))
