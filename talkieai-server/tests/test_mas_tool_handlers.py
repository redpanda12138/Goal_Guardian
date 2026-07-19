import asyncio
import importlib
import sys
import types
from pathlib import Path

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def handlers_runtime(monkeypatch):
    monkeypatch.syspath_prepend(str(SERVER_ROOT))
    dashboard_module = types.ModuleType("app.services.mas.coach_dashboard_service")
    dashboard_module.CoachDashboardService = type("CoachDashboardService", (), {})
    gateway_module = types.ModuleType("app.services.mas.mas_gateway_service")
    gateway_module.MASGatewayService = type("MASGatewayService", (), {})
    mapping_module = types.ModuleType("app.services.mas.patient_mapping_service")
    mapping_module.PatientMappingService = type("PatientMappingService", (), {})
    monkeypatch.setitem(
        sys.modules, "app.services.mas.coach_dashboard_service", dashboard_module
    )
    monkeypatch.setitem(sys.modules, "app.services.mas.mas_gateway_service", gateway_module)
    monkeypatch.setitem(
        sys.modules, "app.services.mas.patient_mapping_service", mapping_module
    )
    module = importlib.import_module("app.services.mas.tool_handlers")
    models = importlib.import_module("app.models.mas_workflow_models")
    return module, models


def test_account_handlers_delegate_to_existing_dashboard_and_oa_services(
    monkeypatch, handlers_runtime
):
    module, models = handlers_runtime
    calls = []
    fake_db = object()

    async def build_dashboard(db, account_id, window):
        calls.append(("dashboard", db, account_id, window))
        return {
            "weekly_progress": {"completed": 2, "total": 3, "rate": 66.7},
            "goals_detail": [{"index": 0, "completed": True}],
            "ignored": "not exposed to the model",
        }

    async def apply_state_event(db, account_id, event_type, goal_index, note):
        calls.append(("state", db, account_id, event_type, goal_index, note))
        return {"ok": True, "changed": True, "event_type": event_type}

    class Mapping:
        def __init__(self, db):
            assert db is fake_db

        def get_or_create_patient_id(self, account_id):
            assert account_id == "account-123"
            return "patient-123"

    async def call_mas_service(service, endpoint, data):
        calls.append(("gateway", service, endpoint, data))
        return {"status": "received", "patients": 1}

    monkeypatch.setattr(
        module.CoachDashboardService, "build_dashboard", build_dashboard, raising=False
    )
    monkeypatch.setattr(
        module.CoachDashboardService, "apply_state_event", apply_state_event, raising=False
    )
    monkeypatch.setattr(module, "PatientMappingService", Mapping)
    monkeypatch.setattr(
        module.MASGatewayService, "call_mas_service", call_mas_service, raising=False
    )

    handlers = module.build_account_tool_handlers(fake_db, "account-123")
    progress = asyncio.run(
        handlers[models.ToolName.GET_WEEKLY_PROGRESS]({"window": "10"})
    )
    completed = asyncio.run(
        handlers[models.ToolName.MARK_GOAL_COMPLETE](
            {"goal_index": 1, "note": "Done"}
        )
    )
    scheduled = asyncio.run(
        handlers[models.ToolName.RESCHEDULE_REVIEW](
            {"date": "2030-07-20T09:00:00+08:00"}
        )
    )

    assert progress == {
        "weekly_progress": {"completed": 2, "total": 3, "rate": 66.7},
        "goals": [{"index": 0, "completed": True}],
    }
    assert completed == {"ok": True, "changed": True, "event_type": "goal_completed"}
    assert scheduled == {"status": "received", "patients": 1}
    assert ("dashboard", fake_db, "account-123", "10") in calls
    assert ("state", fake_db, "account-123", "goal_completed", 1, "Done") in calls
    assert (
        "gateway",
        "oa",
        "/new_sessions",
        [{"study_id": "patient-123", "date": "2030-07-20T09:00:00+08:00"}],
    ) in calls


def test_openai_tool_catalog_exposes_strict_json_schemas(handlers_runtime):
    module, _models = handlers_runtime

    catalog = module.openai_tool_catalog()

    assert [item["function"]["name"] for item in catalog] == [
        "get_weekly_progress",
        "mark_goal_complete",
        "reschedule_review",
    ]
    for item in catalog:
        assert item["type"] == "function"
        assert item["function"]["parameters"]["additionalProperties"] is False
    assert catalog[1]["function"]["parameters"]["required"] == ["goal_index"]
    assert catalog[2]["function"]["parameters"]["required"] == ["date"]
