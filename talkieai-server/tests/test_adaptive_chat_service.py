import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("TOKEN_EXPIRE_TIME", "3600")


@pytest.mark.parametrize("completed", [False, True])
def test_chat_service_uses_explicit_adaptive_completion_and_persists_reply(monkeypatch, completed):
    from app.db import Base
    from app.db.chat_entities import MessageSessionEntity, MessageEntity
    from app.models.chat_models import ChatDTO
    from app.services.chat_service import ChatService
    from app.services.mas.patient_mapping_service import PatientMappingService
    from app.services.mas.mas_gateway_service import MASGatewayService
    from app.config import Config
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(MessageSessionEntity(id="session", account_id="owner", type="MAS", completed=0, deleted=0))
    db.commit()
    monkeypatch.setattr(Config, "MAS_OA_GRAPH_SEAM_ENABLED", True)
    monkeypatch.setattr(Config, "MAS_OA_GRAPH_SHADOW_ENABLED", False)
    monkeypatch.setattr(Config, "MAS_OA_GRAPH_TEST_ACCOUNTS", "")
    monkeypatch.setattr(PatientMappingService, "get_or_create_patient_id", lambda *_: "p")
    identity = {"workflow_mode": "adaptive_v1", "workflow_version": "oa_adaptive_v1", "session_generation": 1}
    calls = []
    async def gateway(service, path, **kwargs):
        calls.append(path)
        if path.startswith("/session_status"):
            return {"status": "ok", **identity, "turn_index": 20, "session_status": "active"}
        if path.startswith("/workflow_mode"):
            return {"status": "ok", **identity}
        assert path == "/adaptive_v1/user_turn"
        return {"status": "ok", **identity, "turn_index": 21, "stage_count": 1,
            "session_status": "completed" if completed else "active", "persisted": True,
            "assistant_message": "The review is recorded.", "retrieval_results": []}
    monkeypatch.setattr(MASGatewayService, "call_mas_service", gateway)
    result = ChatService(db).send_mas_session_message("session", ChatDTO(message="Review response"), "owner")
    assert result["completed"] is completed
    assert db.query(MessageEntity).count() == 2
    assert db.query(MessageSessionEntity).first().completed == int(completed)
    assert calls == ["/session_status/p", "/workflow_mode/p", "/adaptive_v1/user_turn"]
    db.close()
    engine.dispose()
