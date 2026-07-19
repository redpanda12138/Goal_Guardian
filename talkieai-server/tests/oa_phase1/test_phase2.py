from unittest.mock import patch
from copy import deepcopy
from threading import Thread

import pytest
from fastapi.testclient import TestClient

import app as oa_app
import workflow_phase2
from workflow_phase2 import reserve_graph_dispatch, reset_active_sessions, reset_and_latch, reset_patient_session, session_identity


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
    decision, status = reserve_graph_dispatch(lambda: records, lambda value: None, "p", 3, f"r-{turn}", turn)
    assert (decision.selected_agent, status) == (agent, "reserved")


def test_duplicate_conflict_and_stale_generation_are_rejected_or_idempotent():
    records = [{"patient_id": "p", "workflow_mode": "graph_v1", "workflow_version": "oa_graph_v1", "session_generation": 2}]
    reserve_graph_dispatch(lambda: records, lambda value: None, "p", 2, "same", 6)
    duplicate, status = reserve_graph_dispatch(lambda: records, lambda value: None, "p", 2, "same", 6)
    assert (duplicate.selected_agent, status) == ("GRA", "reserved")
    with pytest.raises(ValueError, match="stale_session_generation"):
        reserve_graph_dispatch(lambda: records, lambda value: None, "p", 1, "stale", 6)
    conflict, status = reserve_graph_dispatch(lambda: records, lambda value: None, "p", 2, "conflict", 6, "agent_transition_intent", "SCA")
    assert (conflict.route_status, conflict.selected_agent, status) == ("error", None, "conflict")


def test_graph_ingress_dispatches_once_without_holding_reservation_lock():
    records = [{"patient_id": "p", "workflow_mode": "graph_v1", "workflow_version": "oa_graph_v1", "session_generation": 2}]
    lock_was_free = []
    def fake_trigger(patient_id, turn_index, agent, user_input):
        acquired = workflow_phase2._reservation_lock.acquire(blocking=False)
        lock_was_free.append(acquired)
        if acquired:
            workflow_phase2._reservation_lock.release()
        return {"status": "ok"}
    with patch.object(oa_app, "load_goal_reviews", return_value=records), patch.object(oa_app, "save_goal_reviews"), patch.object(oa_app, "dispatch_graph_user_message_sync", side_effect=fake_trigger):
        client = TestClient(oa_app.app)
        payload = {"patient_id": "p", "session_generation": 2, "request_id": "r", "turn_index": 6, "user_input": "hello"}
        first = client.post("/graph_v1/user_turn", json=payload).json()
        second = client.post("/graph_v1/user_turn", json=payload).json()
    assert first["selected_agent"] == "GRA"
    assert second["message"] == "duplicate_ignored"
    assert lock_was_free == [True]
    assert records[0]["chat_history"] == [{"role": "user", "content": "hello"}]
    assert records[0]["graph_transition_reservations"]["r"]["status"] == "completed"


def test_independent_stale_snapshots_cannot_create_duplicate_reservations():
    durable = {"records": [{"patient_id": "p", "workflow_mode": "graph_v1", "workflow_version": "oa_graph_v1", "session_generation": 2}]}
    saves = []
    def load():
        return deepcopy(durable["records"])
    def save(records):
        durable["records"] = deepcopy(records)
        saves.append(deepcopy(records))
    results = []
    def reserve():
        results.append(reserve_graph_dispatch(load, save, "p", 2, "same", 6, user_input="hello")[1])
    threads = [Thread(target=reserve), Thread(target=reserve)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    record = durable["records"][0]
    assert results == ["reserved", "reserved"]
    assert list(record["graph_transition_reservations"]) == ["same"]
    assert record["chat_history"] == [{"role": "user", "content": "hello"}]
    assert len(saves) == 1


def test_reset_and_ingress_share_one_atomic_generation_boundary(monkeypatch):
    monkeypatch.setenv("OA_LANGGRAPH_NEW_SESSIONS_ENABLED", "true")
    durable = {"records": [{"patient_id": "p", "workflow_mode": "graph_v1", "workflow_version": "oa_graph_v1", "session_generation": 2, "turn_index": 6, "chat_history": []}]}
    def load():
        return deepcopy(durable["records"])
    def save(records):
        durable["records"] = deepcopy(records)
    errors = []
    def reserve():
        try:
            reserve_graph_dispatch(load, save, "p", 2, "r", 6, user_input="hello")
        except ValueError as error:
            errors.append(str(error))
    threads = [Thread(target=reserve), Thread(target=lambda: reset_patient_session(load, save, "p"))]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    record = durable["records"][0]
    assert record["session_generation"] == 3
    assert record["workflow_mode"] == "graph_v1"
    assert record["graph_transition_reservations"] == {}
    assert record["chat_history"] == []
    assert errors in ([], ["stale_session_generation"])


def test_batch_reset_uses_the_same_atomic_latch_helper(monkeypatch):
    monkeypatch.setenv("OA_LANGGRAPH_NEW_SESSIONS_ENABLED", "false")
    records = [{"patient_id": "p", "workflow_mode": "graph_v1", "workflow_version": "oa_graph_v1", "session_generation": 4, "turn_index": 1, "chat_history": [{"role": "user", "content": "x"}], "graph_transition_reservations": {"r": {"status": "completed", "agent": "SOA"}}}]
    assert reset_active_sessions(lambda: records, lambda value: None) == 1
    assert session_identity(records[0]) == {"workflow_mode": "legacy", "workflow_version": "legacy", "session_generation": 5}
    assert records[0]["graph_transition_reservations"] == {}


def test_dispatch_failure_is_indeterminate_and_retry_is_not_false_success():
    records = [{"patient_id": "p", "workflow_mode": "graph_v1", "workflow_version": "oa_graph_v1", "session_generation": 2}]
    calls = []
    def fail(*args):
        calls.append(args)
        raise TimeoutError("ambiguous downstream timeout")
    with patch.object(oa_app, "load_goal_reviews", return_value=records), patch.object(oa_app, "save_goal_reviews"), patch.object(oa_app, "dispatch_graph_user_message_sync", side_effect=fail):
        client = TestClient(oa_app.app)
        payload = {"patient_id": "p", "session_generation": 2, "request_id": "failed", "turn_index": 6, "user_input": "hello"}
        first = client.post("/graph_v1/user_turn", json=payload).json()
        second = client.post("/graph_v1/user_turn", json=payload).json()
    assert first["reason"] == "dispatch_indeterminate"
    assert second == {"status": "error", "reason": "dispatch_indeterminate"}
    assert len(calls) == 1
    assert records[0]["graph_transition_reservations"]["failed"]["status"] == "indeterminate"


def test_graph_trigger_agent_uses_the_same_indeterminate_at_most_once_semantics():
    records = [{"patient_id": "p", "workflow_mode": "graph_v1", "workflow_version": "oa_graph_v1", "session_generation": 2}]
    with patch.object(oa_app, "load_goal_reviews", return_value=records), patch.object(oa_app, "save_goal_reviews"), patch.object(oa_app, "trigger_agent_sync", return_value={"status": "error", "reason": "timeout"}) as trigger:
        client = TestClient(oa_app.app)
        payload = {"patient_id": "p", "session_generation": 2, "request_id": "transition", "turn_index": 6, "agent_to_trigger": "GRA"}
        first = client.post("/trigger_agent", json=payload).json()
        second = client.post("/trigger_agent", json=payload).json()
    assert first["reason"] == "dispatch_indeterminate"
    assert second == {"status": "error", "reason": "dispatch_indeterminate"}
    assert trigger.call_count == 1


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
