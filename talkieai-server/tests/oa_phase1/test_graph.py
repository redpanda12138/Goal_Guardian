import pytest
from pathlib import Path
from workflow_phase1.graph import build_phase1_graph, invoke_phase1_graph

BASE = {"patient_id": "p-1", "session_generation": 1, "workflow_version": "oa_graph_v1", "request_id": "r-1", "event_type": "user_turn", "turn_index": 0, "session_status": "active"}

def test_graph_has_no_checkpointer():
    assert build_phase1_graph().checkpointer is None

@pytest.mark.parametrize("turn,expected", [(0,"SOA"),(6,"GRA"),(14,"SCA"),(15,None)])
def test_every_boundary_terminates(turn, expected):
    decision = invoke_phase1_graph({**BASE, "turn_index": turn, "session_status": "completed" if turn == 15 else "active"})
    assert decision.selected_agent == expected

def test_invalid_and_transition_paths_terminate_without_side_effects():
    invalid = invoke_phase1_graph({**BASE, "turn_index": True})
    assert (invalid.route_status, invalid.selected_agent) == ("error", None)
    approved = invoke_phase1_graph({**BASE, "event_type": "agent_transition_intent", "turn_index": 6, "requested_agent": "GRA"})
    assert (approved.route_status, approved.selected_agent) == ("ready", "GRA")
    conflict = invoke_phase1_graph({**BASE, "event_type": "agent_transition_intent", "turn_index": 6, "requested_agent": "SCA"})
    assert (conflict.route_status, conflict.selected_agent) == ("error", None)

def test_workflow_source_is_pure():
    package = Path(__file__).resolve().parents[2] / "mas" / "OA" / "workflow_phase1"
    source = "\n".join(path.read_text(encoding="utf-8") for path in package.glob("*.py"))
    for forbidden in ("requests", "httpx", "mas_memory_store", "psycopg", "msgpack", "receive_message", "trigger_agent", "serializer", "database"):
        assert forbidden not in source
