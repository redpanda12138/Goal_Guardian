import asyncio
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SQL_ECHO", "false")
os.environ.setdefault("TOKEN_EXPIRE_TIME", "3600")

from app.services.mas.adaptive_bridge import is_completed, notify_tool


def test_adaptive_completion_depends_on_status_not_turn_count():
    assert not is_completed({"workflow_mode": "adaptive_v1", "turn_index": 20, "session_status": "active"})
    assert not is_completed({"workflow_mode": "adaptive_v1", "turn_index": 20, "session_status": "paused"})
    assert is_completed({"workflow_mode": "adaptive_v1", "turn_index": 9, "session_status": "completed"})


def test_tool_notification_uses_original_generation_and_operation():
    calls = []
    class Gateway:
        async def call_mas_service(self, service, endpoint, **kwargs):
            calls.append((service, endpoint, kwargs))
            return {"status": "ok", "persisted": True, "assistant_message": ""}
    identity = {"workflow_mode": "adaptive_v1", "workflow_version": "oa_adaptive_v1",
                "session_generation": 2, "operation_id": "original-request"}
    asyncio.run(notify_tool(Gateway(), "p", identity, "succeeded", {"changed": True}))
    assert calls[0][1] == "/adaptive_v1/tool_event"
    assert calls[0][2]["data"]["session_generation"] == 2
    assert calls[0][2]["data"]["operation_id"] == "original-request"
