"""Pure identity and ownership helpers for the new MAS workflow boundary."""
import uuid
from typing import Any


class SessionOwnershipError(PermissionError):
    """Raised when a workflow request does not own the requested MAS session."""


def derive_thread_id(account_id: str, mas_session_id: str, workflow_version: str) -> str:
    """Derive a stable thread identifier without storing a second source of truth."""
    components = (account_id, mas_session_id, workflow_version)
    if any(not isinstance(component, str) or not component for component in components):
        raise ValueError("account, MAS session, and workflow version are required")
    seed = "goalguardian.workflow:" + ":".join(components)
    return "ggwf-" + uuid.uuid5(uuid.NAMESPACE_URL, seed).hex


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
