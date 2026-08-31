import asyncio
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("TOKEN_EXPIRE_TIME", "3600")


def test_control_is_account_scoped_and_only_cancels_oa_cancelled_operations(monkeypatch):
    from app.api import mas_routes
    from app.db import Base
    from app.db.chat_entities import MessageSessionEntity
    from app.models.mas_models import AdaptiveSessionControlDTO
    from app.models.mas_workflow_models import ToolRequest, ToolName
    from app.services.mas.pending_tool_confirmation import PendingToolConfirmationStore
    from fastapi import HTTPException
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(MessageSessionEntity(id="session", account_id="owner", type="MAS", deleted=0, completed=0))
    store = PendingToolConfirmationStore(db)
    request = ToolRequest(tool_name=ToolName.MARK_GOAL_COMPLETE, arguments={"goal_index": 0}, requires_confirmation=True)
    identity = {"workflow_mode": "adaptive_v1", "workflow_version": "oa_adaptive_v1", "session_generation": 2}
    first = store.create("owner", "session", "m1", 20, request, workflow_identity={**identity, "operation_id": "one"})
    second = store.create("owner", "session", "m2", 21, request, workflow_identity={**identity, "operation_id": "two"})
    db.commit()
    monkeypatch.setattr(mas_routes.PatientMappingService, "get_or_create_patient_id", lambda *_: "mapped-owner")
    calls = []
    async def gateway(service, endpoint, **kwargs):
        calls.append(kwargs["data"])
        return {"status": "ok", "session_status": "paused", "cancelled_operations": ["one"]}
    monkeypatch.setattr(mas_routes.MASGatewayService, "call_mas_service", gateway)
    dto = AdaptiveSessionControlDTO(session_id="session", session_generation=2, command="stop")
    with pytest.raises(HTTPException):
        asyncio.run(mas_routes.control_adaptive_session(dto, db, "other"))
    assert not calls
    asyncio.run(mas_routes.control_adaptive_session(dto, db, "owner"))
    assert calls[0]["patient_id"] == "mapped-owner"
    assert store.get(first["action_id"], "owner")["status"] == "cancelled"
    assert store.get(second["action_id"], "owner")["status"] == "pending"
    db.close()
    engine.dispose()
