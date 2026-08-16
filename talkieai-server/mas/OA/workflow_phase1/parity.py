from .contracts import AgentName, GraphState, RouteDecision

def select_active_agent(turn_index: int) -> AgentName:
    if type(turn_index) is not int or not 0 <= turn_index <= 14:
        raise ValueError("active turn_index must be between 0 and 14")
    if turn_index <= 5:
        return "SOA"
    if turn_index <= 13:
        return "GRA"
    return "SCA"

def decide_legacy_parity(state: GraphState) -> RouteDecision:
    if state["turn_index"] == 15 or state["session_status"] == "completed":
        return RouteDecision(None, "session_completed", "completed")
    return RouteDecision(select_active_agent(state["turn_index"]), "canonical_legacy_parity", "ready")
