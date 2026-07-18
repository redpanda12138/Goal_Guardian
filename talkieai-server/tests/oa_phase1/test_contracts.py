import pytest
from workflow_phase1.contracts import validate_graph_input

VALID = {"patient_id": "p-1", "session_generation": 2, "workflow_version": "oa_graph_v1", "request_id": "r-1", "event_type": "user_turn", "turn_index": 6, "session_status": "active"}

def test_validate_graph_input_returns_json_safe_state():
    assert validate_graph_input(VALID)["turn_index"] == 6

def test_validate_graph_input_rejects_binary_and_out_of_range():
    with pytest.raises(ValueError, match="JSON-compatible"):
        validate_graph_input({**VALID, "patient_id": b"p-1"})
    with pytest.raises(ValueError, match="between 0 and 15"):
        validate_graph_input({**VALID, "turn_index": 16})

@pytest.mark.parametrize("patch,message", [({"turn_index": True}, "turn_index"), ({"event_type": "model_decides"}, "event_type"), ({"session_status": "unknown"}, "session_status"), ({"session_generation": 0}, "session_generation"), ({"patient_id": ""}, "patient_id"), ({"requested_agent": "MMA", "event_type": "agent_transition_intent"}, "requested_agent"), ({"unexpected": "value"}, "unknown graph field"), ({"request_id": lambda: None}, "JSON-compatible")])
def test_validate_graph_input_rejects_strict_boundary_violations(patch, message):
    with pytest.raises(ValueError, match=message):
        validate_graph_input({**VALID, **patch})

def test_missing_and_transition_requirements_are_strict():
    incomplete = dict(VALID); incomplete.pop("request_id")
    with pytest.raises(ValueError, match="missing required"):
        validate_graph_input(incomplete)
    with pytest.raises(ValueError, match="requested_agent is required"):
        validate_graph_input({**VALID, "event_type": "agent_transition_intent"})
