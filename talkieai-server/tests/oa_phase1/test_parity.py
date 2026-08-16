import pytest
from workflow_phase1.contracts import RouteDecision
from workflow_phase1.parity import decide_legacy_parity, select_active_agent

BASE = {"patient_id": "p-1", "session_generation": 1, "workflow_version": "oa_graph_v1", "request_id": "r-1", "event_type": "user_turn", "turn_index": 0, "session_status": "active"}

@pytest.mark.parametrize("turn,agent", [(0,"SOA"),(5,"SOA"),(6,"GRA"),(13,"GRA"),(14,"SCA")])
def test_active_boundaries_match_canonical_selector(turn, agent):
    assert select_active_agent(turn) == agent

@pytest.mark.parametrize("status,turn", [("active", 15), ("completed", 14)])
def test_completion_guard_precedes_selector(status, turn):
    assert decide_legacy_parity({**BASE, "turn_index": turn, "session_status": status}) == RouteDecision(None, "session_completed", "completed")
