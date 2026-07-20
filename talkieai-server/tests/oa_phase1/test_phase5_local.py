from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app as oa_app
import workflow_phase2
from workflow_phase1.graph import invoke_phase1_graph


@pytest.mark.parametrize(
    "record,expected_stage,expected_phase",
    [
        (
            {
                "workflow_mode": "graph_v1",
                "workflow_version": "oa_graph_v1",
                "turn_index": 0,
                "chat_history": [],
            },
            "opening",
            "opening",
        ),
        (
            {
                "workflow_mode": "graph_v1",
                "workflow_version": "oa_graph_v1",
                "turn_index": 6,
                "chat_history": [{"role": "user", "content": "review"}],
            },
            "review_decision",
            "review_decision",
        ),
        (
            {
                "workflow_mode": "graph_v1",
                "workflow_version": "oa_graph_v1",
                "turn_index": 7,
                "chat_history": [{"role": "assistant", "content": "question"}],
            },
            "waiting_user",
            "review_decision",
        ),
        (
            {
                "workflow_mode": "graph_v1",
                "workflow_version": "oa_graph_v1",
                "turn_index": 14,
                "chat_history": [{"role": "user", "content": "close"}],
            },
            "closing",
            "closing",
        ),
        (
            {
                "workflow_mode": "graph_v1",
                "workflow_version": "oa_graph_v1",
                "turn_index": 15,
                "chat_history": [],
            },
            "summary",
            "summary",
        ),
    ],
)
def test_graph_workflow_projection_covers_the_complete_review_path(
    record, expected_stage, expected_phase
):
    projection = workflow_phase2.workflow_projection(record)

    assert projection["workflow_stage"] == expected_stage
    assert projection["workflow_phase"] == expected_phase


def test_legacy_record_has_no_graph_stage_projection():
    assert workflow_phase2.workflow_projection(
        {"workflow_mode": "legacy", "turn_index": 6}
    ) == {}


def test_turn_15_summary_transition_is_routable_but_a_user_turn_is_complete():
    transition = invoke_phase1_graph(
        {
            "patient_id": "patient-1",
            "session_generation": 2,
            "workflow_version": "oa_graph_v1",
            "request_id": "summary-transition",
            "event_type": "agent_transition_intent",
            "requested_agent": "SSA",
            "turn_index": 15,
            "session_status": "completed",
        }
    )
    user_turn = invoke_phase1_graph(
        {
            "patient_id": "patient-1",
            "session_generation": 2,
            "workflow_version": "oa_graph_v1",
            "request_id": "late-user-turn",
            "event_type": "user_turn",
            "turn_index": 15,
            "session_status": "completed",
        }
    )

    assert (transition.selected_agent, transition.route_status) == ("SSA", "ready")
    assert (user_turn.selected_agent, user_turn.route_status) == (None, "completed")


def test_graph_identity_and_session_status_expose_the_same_stage_projection():
    record = {
        "patient_id": "patient-1",
        "workflow_mode": "graph_v1",
        "workflow_version": "oa_graph_v1",
        "session_generation": 2,
        "turn_index": 7,
        "chat_history": [{"role": "assistant", "content": "question"}],
    }
    with patch.object(oa_app, "load_goal_reviews", return_value=[record]):
        client = TestClient(oa_app.app)
        identity = client.get("/workflow_mode/patient-1").json()
        status = client.get("/session_status/patient-1").json()

    assert identity["workflow_stage"] == "waiting_user"
    assert status["workflow_stage"] == "waiting_user"
    assert identity["workflow_phase"] == status["workflow_phase"] == "review_decision"


@pytest.mark.parametrize(
    "turn,expected_agent",
    [(0, "SOA"), (6, "GRA"), (14, "SCA"), (15, None)],
)
def test_shadow_endpoint_compares_routes_without_any_side_effects(
    turn, expected_agent
):
    with (
        patch.object(oa_app, "load_goal_reviews") as load,
        patch.object(oa_app, "save_goal_reviews") as save,
        patch.object(oa_app, "dispatch_graph_user_message_sync") as dispatch,
        patch.object(oa_app, "trigger_agent_sync") as trigger,
    ):
        response = TestClient(oa_app.app).post(
            "/graph_v1/shadow_decision",
            json={
                "patient_id": "patient-shadow",
                "request_id": f"shadow-{turn}",
                "turn_index": turn,
                "session_status": "completed" if turn == 15 else "active",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "matched": True,
        "legacy_selected_agent": expected_agent,
        "graph_selected_agent": expected_agent,
        "graph_route_status": "completed" if turn == 15 else "ready",
    }
    load.assert_not_called()
    save.assert_not_called()
    dispatch.assert_not_called()
    trigger.assert_not_called()


def test_new_graph_sessions_can_be_restricted_to_test_patients(monkeypatch):
    monkeypatch.setenv("OA_LANGGRAPH_NEW_SESSIONS_ENABLED", "true")
    monkeypatch.setenv("OA_LANGGRAPH_TEST_PATIENTS", "patient-enabled, patient-two")

    enabled = {"patient_id": "patient-enabled"}
    excluded = {"patient_id": "patient-other"}
    workflow_phase2.reset_and_latch(enabled)
    workflow_phase2.reset_and_latch(excluded)

    assert workflow_phase2.session_identity(enabled)["workflow_mode"] == "graph_v1"
    assert workflow_phase2.session_identity(excluded)["workflow_mode"] == "legacy"


def test_disabling_allocation_preserves_an_active_graph_generation(monkeypatch):
    monkeypatch.setenv("OA_LANGGRAPH_NEW_SESSIONS_ENABLED", "false")
    monkeypatch.setenv("OA_LANGGRAPH_TEST_PATIENTS", "patient-enabled")
    active = {
        "patient_id": "patient-enabled",
        "workflow_mode": "graph_v1",
        "workflow_version": "oa_graph_v1",
        "session_generation": 4,
    }

    assert workflow_phase2.session_identity(active)["workflow_mode"] == "graph_v1"
