from copy import deepcopy

from workflow_phase2 import (
    reserve_graph_dispatch,
    reset_patient_session,
    session_identity,
)


def _durable_store(records):
    durable = {"records": deepcopy(records)}

    def load():
        return deepcopy(durable["records"])

    def save(updated):
        durable["records"] = deepcopy(updated)

    return durable, load, save


def test_restart_reconstructs_completed_request_without_redispatch():
    durable, load, save = _durable_store([
        {
            "patient_id": "p",
            "workflow_mode": "graph_v1",
            "workflow_version": "oa_graph_v1",
            "session_generation": 7,
            "graph_transition_reservations": {
                "completed-request": {"status": "completed", "agent": "GRA"}
            },
        }
    ])

    # A fresh loader represents a restarted OA process reading business state.
    decision, status = reserve_graph_dispatch(
        load, save, "p", 7, "completed-request", 6, user_input="same request"
    )

    assert (decision.selected_agent, status) == ("GRA", "completed")
    assert durable["records"][0]["graph_transition_reservations"] == {
        "completed-request": {"status": "completed", "agent": "GRA"}
    }
    assert "chat_history" not in durable["records"][0]


def test_restart_fails_closed_for_ambiguous_inflight_request():
    durable, load, save = _durable_store([
        {
            "patient_id": "p",
            "workflow_mode": "graph_v1",
            "workflow_version": "oa_graph_v1",
            "session_generation": 7,
            "graph_transition_reservations": {
                "inflight-request": {"status": "dispatching", "agent": "SCA"}
            },
        }
    ])

    decision, status = reserve_graph_dispatch(
        load, save, "p", 7, "inflight-request", 14, user_input="same request"
    )

    assert (decision.selected_agent, status) == ("SCA", "dispatching")
    assert durable["records"][0]["graph_transition_reservations"]["inflight-request"]["status"] == "dispatching"
    assert "chat_history" not in durable["records"][0]


def test_rollout_off_returns_only_the_next_generation_to_legacy(monkeypatch):
    monkeypatch.setenv("OA_LANGGRAPH_NEW_SESSIONS_ENABLED", "false")
    durable, load, save = _durable_store([
        {
            "patient_id": "p",
            "workflow_mode": "graph_v1",
            "workflow_version": "oa_graph_v1",
            "session_generation": 7,
            "turn_index": 6,
            "chat_history": [{"role": "user", "content": "current generation"}],
        }
    ])

    assert session_identity(load()[0])["workflow_mode"] == "graph_v1"
    reset_patient_session(load, save, "p")

    assert session_identity(durable["records"][0]) == {
        "workflow_mode": "legacy",
        "workflow_version": "legacy",
        "session_generation": 8,
    }
