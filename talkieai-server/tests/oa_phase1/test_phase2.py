from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app as oa_app
import workflow_phase2
from workflow_phase2 import reserve_graph_dispatch, reset_and_latch, session_identity


def test_flag_defaults_off_and_latches_only_on_reset(monkeypatch):
    monkeypatch.delenv("OA_LANGGRAPH_NEW_SESSIONS_ENABLED", raising=False)
    old = {"patient_id": "p", "turn_index": 4}
    assert session_identity(old) == {"workflow_mode": "legacy", "workflow_version": "legacy", "session_generation": 1}
    reset_and_latch(old)
    assert session_identity(old) == {"workflow_mode": "legacy", "workflow_version": "legacy", "session_generation": 1}
    monkeypatch.setenv("OA_LANGGRAPH_NEW_SESSIONS_ENABLED", "true")
    assert session_identity(old)["workflow_mode"] == "legacy"
    reset_and_latch(old)
    assert session_identity(old) == {"workflow_mode": "graph_v1", "workflow_version": "oa_graph_v1", "session_generation": 2}
    monkeypatch.setenv("OA_LANGGRAPH_NEW_SESSIONS_ENABLED", "false")
    assert session_identity(old)["workflow_mode"] == "graph_v1"


@pytest.mark.parametrize("turn,agent", [(0, "SOA"), (5, "SOA"), (6, "GRA"), (13, "GRA"), (14, "SCA")])
def test_graph_reservation_uses_phase1_boundaries(turn, agent):
    records = [{"patient_id": "p", "workflow_mode": "graph_v1", "workflow_version": "oa_graph_v1", "session_generation": 3}]
    decision, status = reserve_graph_dispatch(records, "p", 3, f"r-{turn}", turn)
    assert (decision.selected_agent, status) == (agent, "reserved")


def test_duplicate_conflict_and_stale_generation_are_rejected_or_idempotent():
    records = [{"patient_id": "p", "workflow_mode": "graph_v1", "workflow_version": "oa_graph_v1", "session_generation": 2}]
    reserve_graph_dispatch(records, "p", 2, "same", 6)
    assert reserve_graph_dispatch(records, "p", 2, "same", 6) == (None, "reserved")
    with pytest.raises(ValueError, match="stale_session_generation"):
        reserve_graph_dispatch(records, "p", 1, "stale", 6)
    conflict, status = reserve_graph_dispatch(records, "p", 2, "conflict", 6, "agent_transition_intent", "SCA")
    assert (conflict.route_status, conflict.selected_agent, status) == ("error", None, "conflict")


def test_graph_ingress_dispatches_once_without_holding_reservation_lock():
    records = [{"patient_id": "p", "workflow_mode": "graph_v1", "workflow_version": "oa_graph_v1", "session_generation": 2}]
    lock_was_free = []
    def fake_trigger(patient_id, turn_index, agent):
        acquired = workflow_phase2._reservation_lock.acquire(blocking=False)
        lock_was_free.append(acquired)
        if acquired:
            workflow_phase2._reservation_lock.release()
        return {"status": "ok"}
    with patch.object(oa_app, "load_goal_reviews", return_value=records), patch.object(oa_app, "save_goal_reviews"), patch.object(oa_app, "trigger_agent_sync", side_effect=fake_trigger):
        client = TestClient(oa_app.app)
        payload = {"patient_id": "p", "session_generation": 2, "request_id": "r", "turn_index": 6}
        first = client.post("/graph_v1/user_turn", json=payload).json()
        second = client.post("/graph_v1/user_turn", json=payload).json()
    assert first["selected_agent"] == "GRA"
    assert second["message"] == "duplicate_ignored"
    assert lock_was_free == [True]


def test_legacy_trigger_endpoint_remains_exact_when_flag_is_off(monkeypatch):
    monkeypatch.setenv("OA_LANGGRAPH_NEW_SESSIONS_ENABLED", "false")
    records = [{"patient_id": "p", "turn_index": 1}]
    with patch.object(oa_app, "load_goal_reviews", return_value=records), patch.object(oa_app, "trigger_agent_sync", return_value={"status": "ok"}) as trigger:
        response = TestClient(oa_app.app).post("/trigger_agent", json={"patient_id": "p", "turn_index": 1, "agent_to_trigger": "SOA"})
    assert response.json() == {"status": "ok"}
    trigger.assert_called_once_with("p", 1, "SOA")


def test_production_requirements_use_modern_runtime_without_probe_tools():
    text = (oa_app.Path(__file__).resolve().parents[2] / "mas" / "OA" / "requirements.txt").read_text(encoding="utf-8")
    assert "langgraph==1.2.9" in text
    assert "requests==2.34.2" in text
    assert "pytest" not in text and "pip-audit" not in text
