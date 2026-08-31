import pytest
from fastapi.testclient import TestClient

import app as oa_app
import adaptive_routes
from adaptive_workflow import AdaptiveWorkflow
from adaptive_policy import CRITERIA
from mas_memory_store import reset_engine_cache


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "routes.db"))
    monkeypatch.setenv("OA_ADAPTIVE_ENABLED", "true")
    reset_engine_cache()
    yield TestClient(oa_app.app)
    reset_engine_cache()


def test_ingress_persists_early_handoff_and_replays_response(client, monkeypatch):
    count = []
    def dispatch(state):
        count.append(1)
        keys = CRITERIA[state["active_agent"]]
        return {"assistant_message": "How is your goal progressing?", "assessment": {
            "decision": "advance", "criteria": {k: True for k in keys},
            "evidence": {k: [state["chat_history"][-1]["id"]] for k in keys}, "reason": "All items recorded."}}
    monkeypatch.setattr(adaptive_routes, "dispatch_stage", dispatch)
    client.post("/adaptive_v1/start", json={"patient_id": "p"})
    for i in range(3):
        body = {"patient_id": "p", "session_generation": 1, "request_id": str(i), "user_input": "response"}
        first = client.post("/adaptive_v1/user_turn", json=body).json()
        assert client.post("/adaptive_v1/user_turn", json=body).json() == first
    assert first["current_agent"] == "GRA"
    assert len(count) == 3
    assert client.get("/session_status/p").json()["workflow_mode"] == "adaptive_v1"
    assert len(client.get("/conversation_history/p").json()["chat_history"]) == 7


def test_control_pause_resume_and_old_generation_rejection(client):
    client.post("/adaptive_v1/start", json={"patient_id": "p"})
    body = {"patient_id": "p", "session_generation": 1, "command": "pause"}
    assert client.post("/adaptive_v1/control", json=body).json()["session_status"] == "paused"
    body["command"] = "resume"
    assert client.post("/adaptive_v1/control", json=body).json()["session_status"] == "active"
    AdaptiveWorkflow("p").reset()
    assert client.post("/adaptive_v1/control", json=body).status_code == 409


def test_assessment_service_failure_does_not_force_switch(client, monkeypatch):
    client.post("/adaptive_v1/start", json={"patient_id": "p"})
    def unavailable(state):
        raise RuntimeError("model offline")
    monkeypatch.setattr(adaptive_routes, "dispatch_stage", unavailable)
    result = client.post("/adaptive_v1/user_turn", json={"patient_id": "p", "session_generation": 1,
        "request_id": "r", "user_input": "hello"}).json()
    assert result["current_agent"] == "SOA"
    assert result["session_status"] == "active"


def test_late_callbacks_are_rejected(client):
    client.post("/adaptive_v1/start", json={"patient_id": "p"})
    for path in ("/receive_message", "/receive_user_message"):
        assert client.post(path, json={"patient_id": "p", "message": "late"}).status_code == 409


def test_summary_recovers_on_status_read_after_failure(client, monkeypatch):
    client.post("/adaptive_v1/start", json={"patient_id": "p"})
    workflow = AdaptiveWorkflow("p")
    workflow.control("stop", 1)
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"status": "ok"}
    calls = []
    def request(*args, **kwargs):
        calls.append(kwargs["json"])
        if len(calls) == 1:
            raise adaptive_routes.requests.ConnectionError("offline")
        return Response()
    monkeypatch.setattr(adaptive_routes.requests, "post", request)
    adaptive_routes.summarise_if_ready(workflow)
    assert workflow.get()["summary_status"] == "indeterminate"
    workflow.update(lambda state: {**state, "summary_lease_until": 0})
    assert client.get("/session_status/p").json()["summary_status"] == "completed"
    assert calls[0]["session_generation"] == calls[1]["session_generation"] == 1
