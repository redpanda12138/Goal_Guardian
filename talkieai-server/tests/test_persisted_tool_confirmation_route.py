import asyncio
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SQL_ECHO", "false")
os.environ.setdefault("TOKEN_EXPIRE_TIME", "3600")


def runtime():
    from app.db import Base
    from app.db.mas_entities import WorkflowToolConfirmationEntity
    from app.models.mas_workflow_models import ToolName, ToolRequest
    from app.services.mas.pending_tool_confirmation import PendingToolConfirmationStore

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    store = PendingToolConfirmationStore(db, WorkflowToolConfirmationEntity)
    request = ToolRequest(
        tool_name=ToolName.MARK_GOAL_COMPLETE,
        arguments={"goal_index": 1},
        requires_confirmation=True,
    )
    action = store.create(
        "account-123", "session-123", "message-123", 8, request
    )
    db.commit()
    return engine, db, store, action


def test_confirmed_route_executes_the_stored_request_and_completes_action(monkeypatch):
    from app.api import mas_routes
    from app.models.mas_models import ResolveWorkflowToolConfirmationDTO
    from app.models.mas_workflow_models import ToolResult, ToolResultStatus
    from app.services.mas import tool_handlers, tool_workflow

    engine, db, store, action = runtime()
    executed = []

    async def execute(_db, account_id, request, confirmed):
        executed.append((account_id, request.dict(), confirmed))
        return ToolResult(
            tool_name=request.tool_name,
            status=ToolResultStatus.SUCCEEDED,
            payload={"changed": True},
        )

    def continuation(_gateway, patient_id, turn_index):
        assert patient_id == "patient-123"
        assert turn_index == 8

        async def run(_result):
            return "Goal 2 has been marked complete."

        return run

    monkeypatch.setattr(tool_handlers, "execute_account_tool", execute)
    monkeypatch.setattr(tool_workflow, "build_gra_continuation", continuation)
    monkeypatch.setattr(
        mas_routes.PatientMappingService,
        "get_or_create_patient_id",
        lambda _self, account_id: "patient-123",
    )

    response = asyncio.run(
        mas_routes.execute_workflow_tool(
            ResolveWorkflowToolConfirmationDTO(
                action_id=action["action_id"], confirmed=True
            ),
            db,
            "account-123",
        )
    )

    assert executed[0][0] == "account-123"
    assert executed[0][1]["arguments"] == {"goal_index": 1}
    assert response.data["assistant_message"] == "Goal 2 has been marked complete."
    assert response.data["action_status"] == "completed"
    assert store.get_for_message("message-123", "account-123")["status"] == "completed"
    db.close()
    engine.dispose()


def test_adaptive_confirmation_checks_oa_before_write_and_reports_terminal_success(monkeypatch):
    from app.api import mas_routes
    from app.models.mas_models import ResolveWorkflowToolConfirmationDTO
    from app.models.mas_workflow_models import ToolResult, ToolResultStatus
    from app.services.mas import tool_handlers, adaptive_bridge

    engine, db, store, initial = runtime()
    request = store._parse_request(db.query(store.entity_model).first().tool_request_json)
    identity = {"workflow_mode": "adaptive_v1", "workflow_version": "oa_adaptive_v1",
                "session_generation": 3, "operation_id": "request-20"}
    action = store.create("account-123", "session-123", "message-20", 20, request, workflow_identity=identity)
    db.commit()
    events = []
    async def notify(gateway, patient, original, status, result=None):
        assert original == identity
        events.append(status)
        if status == "succeeded":
            raise RuntimeError("OA temporarily unavailable")
        return {"status": "ok"}
    async def execute(_db, account, request, confirmed):
        events.append("write")
        return ToolResult(tool_name=request.tool_name, status=ToolResultStatus.SUCCEEDED, payload={"changed": True})
    monkeypatch.setattr(adaptive_bridge, "notify_tool", notify)
    monkeypatch.setattr(tool_handlers, "execute_account_tool", execute)
    monkeypatch.setattr(mas_routes.PatientMappingService, "get_or_create_patient_id", lambda *args: "p")
    result = asyncio.run(mas_routes.execute_workflow_tool(
        ResolveWorkflowToolConfirmationDTO(action_id=action["action_id"], confirmed=True), db, "account-123"))
    assert events == ["executing", "write", "succeeded"]
    assert result.data["action_status"] == "completed"
    assert result.data["continuation_pending"] is True
    assert store.get(action["action_id"], "account-123")["status"] == "completed"
    db.close()
    engine.dispose()


def test_cancel_route_persists_without_executing_a_tool(monkeypatch):
    from app.api import mas_routes
    from app.models.mas_models import ResolveWorkflowToolConfirmationDTO
    from app.services.mas import tool_handlers

    engine, db, store, action = runtime()

    async def must_not_execute(*_args, **_kwargs):
        raise AssertionError("cancel must not execute the tool")

    monkeypatch.setattr(tool_handlers, "execute_account_tool", must_not_execute)
    response = asyncio.run(
        mas_routes.execute_workflow_tool(
            ResolveWorkflowToolConfirmationDTO(
                action_id=action["action_id"], confirmed=False
            ),
            db,
            "account-123",
        )
    )

    assert response.data == {
        "action_id": action["action_id"],
        "action_status": "cancelled",
    }
    assert store.get_for_message("message-123", "account-123")["status"] == "cancelled"
    db.close()
    engine.dispose()
