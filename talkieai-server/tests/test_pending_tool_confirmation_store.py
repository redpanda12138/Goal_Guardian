import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SQL_ECHO", "false")
os.environ.setdefault("TOKEN_EXPIRE_TIME", "3600")


@pytest.fixture
def store_runtime():
    from app.db import Base
    from app.db.chat_entities import MessageEntity  # noqa: F401
    from app.db.mas_entities import WorkflowToolConfirmationEntity
    from app.models.mas_workflow_models import ToolName, ToolRequest
    from app.services.mas.pending_tool_confirmation import (
        PendingActionConflict,
        PendingActionNotFound,
        PendingToolConfirmationStore,
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    store = PendingToolConfirmationStore(db, WorkflowToolConfirmationEntity)
    try:
        yield {
            "db": db,
            "store": store,
            "entity": WorkflowToolConfirmationEntity,
            "ToolName": ToolName,
            "ToolRequest": ToolRequest,
            "Conflict": PendingActionConflict,
            "NotFound": PendingActionNotFound,
        }
    finally:
        db.close()
        engine.dispose()


def write_request(runtime):
    return runtime["ToolRequest"](
        tool_name=runtime["ToolName"].MARK_GOAL_COMPLETE,
        arguments={"goal_index": 1, "note": "Done"},
        requires_confirmation=True,
    )


def test_pending_action_round_trips_for_the_owning_message_after_reload(store_runtime):
    runtime = store_runtime
    created = runtime["store"].create(
        account_id="account-123",
        session_id="session-123",
        message_id="message-123",
        turn_index=8,
        request=write_request(runtime),
    )
    runtime["db"].commit()

    restored = runtime["store"].get_for_message(
        "message-123", "account-123"
    )

    assert restored == {
        "action_id": created["action_id"],
        "tool_request": {
            "contract_version": "v1",
            "tool_name": "mark_goal_complete",
            "arguments": {"goal_index": 1, "note": "Done"},
            "requires_confirmation": True,
        },
        "turn_index": 8,
        "status": "pending",
    }


def test_action_is_account_scoped_and_cannot_be_claimed_twice(store_runtime):
    runtime = store_runtime
    created = runtime["store"].create(
        "account-123", "session-123", "message-123", 8, write_request(runtime)
    )
    runtime["db"].commit()

    with pytest.raises(runtime["NotFound"]):
        runtime["store"].claim(created["action_id"], "account-other")

    claimed = runtime["store"].claim(created["action_id"], "account-123")
    runtime["db"].commit()
    assert claimed.tool_name == runtime["ToolName"].MARK_GOAL_COMPLETE

    with pytest.raises(runtime["Conflict"]):
        runtime["store"].claim(created["action_id"], "account-123")


def test_cancel_is_persisted_and_prevents_later_execution(store_runtime):
    runtime = store_runtime
    created = runtime["store"].create(
        "account-123", "session-123", "message-123", 8, write_request(runtime)
    )
    runtime["db"].commit()

    cancelled = runtime["store"].cancel(created["action_id"], "account-123")
    runtime["db"].commit()

    assert cancelled["status"] == "cancelled"
    assert runtime["store"].get_for_message("message-123", "account-123")[
        "status"
    ] == "cancelled"
    with pytest.raises(runtime["Conflict"]):
        runtime["store"].claim(created["action_id"], "account-123")


@pytest.mark.parametrize(
    "tool_status,expected_status",
    [("succeeded", "completed"), ("failed", "failed")],
)
def test_execution_result_becomes_a_persisted_terminal_state(
    store_runtime, tool_status, expected_status
):
    runtime = store_runtime
    created = runtime["store"].create(
        "account-123", "session-123", "message-123", 8, write_request(runtime)
    )
    runtime["store"].claim(created["action_id"], "account-123")

    finished = runtime["store"].finish(
        created["action_id"], "account-123", tool_status
    )
    runtime["db"].commit()

    assert finished["status"] == expected_status
    assert runtime["store"].get_for_message("message-123", "account-123")[
        "status"
    ] == expected_status


def test_chat_message_serialization_restores_the_confirmation_control(store_runtime):
    from app.db.chat_entities import MessageEntity
    from app.models.chat_models import MessageType
    from app.services.chat_service import ChatService

    runtime = store_runtime
    message = MessageEntity(
        id="message-123",
        session_id="session-123",
        account_id="account-123",
        sender="SYSTEM",
        receiver="account-123",
        type=MessageType.SYSTEM.value,
        content="Would you like me to mark goal 2 complete?",
        length=42,
        sequence=2,
    )
    runtime["db"].add(message)
    runtime["store"].create(
        "account-123", "session-123", "message-123", 8, write_request(runtime)
    )
    runtime["db"].commit()

    service = ChatService.__new__(ChatService)
    service.db = runtime["db"]
    serialized = service.initMessageResult(message)

    assert serialized["tool_confirmation"]["status"] == "pending"
    assert serialized["tool_confirmation"]["action_id"]
    assert serialized["tool_confirmation"]["tool_request"]["tool_name"] == "mark_goal_complete"
