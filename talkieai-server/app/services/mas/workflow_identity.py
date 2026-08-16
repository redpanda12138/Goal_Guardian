"""Pure identity and ownership helpers for the new MAS workflow boundary."""
import json
import re
import uuid
from typing import Any


IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$"


class SessionOwnershipError(PermissionError):
    """Raised when a workflow request does not own the requested MAS session."""


def derive_thread_id(account_id: str, mas_session_id: str, workflow_version: str) -> str:
    """Derive a stable thread identifier without storing a second source of truth."""
    components = (account_id, mas_session_id, workflow_version)
    if any(not isinstance(component, str) or not component for component in components):
        raise ValueError("account, MAS session, and workflow version are required")
    seed = json.dumps(
        ["goalguardian.workflow", *components],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "ggwf-" + uuid.uuid5(uuid.NAMESPACE_URL, seed).hex


def validate_stable_identifier(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(IDENTIFIER_PATTERN, value):
        raise ValueError(f"{field_name} must be a stable identifier")
    return value


def validate_session_ownership(
    session: Any, account_id: str, mas_session_id: str
) -> Any:
    """Validate that the authenticated account owns the requested MAS session."""
    if (
        session is None
        or getattr(session, "id", None) != mas_session_id
        or getattr(session, "account_id", None) != account_id
    ):
        raise SessionOwnershipError("MAS session does not belong to this account")
    return session


class WorkflowSessionOwnershipService:
    """Query-bound validation for an active MAS session owned by an account."""

    def __init__(self, db: Any, session_model: Any = None):
        self.db = db
        self.session_model = session_model

    def get_owned_active_mas_session(self, account_id: str, mas_session_id: str) -> Any:
        model = self.session_model
        if model is None:
            from app.db.chat_entities import MessageSessionEntity

            model = MessageSessionEntity
        session = (
            self.db.query(model)
            .filter_by(
                id=mas_session_id,
                account_id=account_id,
                type="MAS",
                completed=0,
                deleted=0,
            )
            .first()
        )
        return validate_session_ownership(session, account_id, mas_session_id)
