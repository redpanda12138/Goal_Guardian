"""JSON-only checkpoint state helpers for the future MAS workflow."""
from typing import Any, Dict

from app.services.mas.workflow_identity import derive_thread_id


class LegacyCompatStateAdapter:
    """Expose only recoverable legacy facts under the legacy_compat namespace."""

    @staticmethod
    def bootstrap(
        legacy_turn_index: int, legacy_session_status: str
    ) -> Dict[str, Dict[str, Any]]:
        return {
            "legacy_compat": {
                "legacy_turn_index": legacy_turn_index,
                "legacy_session_status": legacy_session_status,
            }
        }


def bootstrap_workflow_state(
    account_id: str,
    mas_session_id: str,
    request_id: str,
    workflow_version: str,
    legacy_compat: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a versioned JSON checkpoint without pending actions or model objects."""
    if set(legacy_compat) != {"legacy_compat"}:
        raise ValueError("legacy adapters may only provide legacy_compat")
    return {
        "state_version": "v1",
        "workflow_version": workflow_version,
        "account_id": account_id,
        "mas_session_id": mas_session_id,
        "request_id": request_id,
        "thread_id": derive_thread_id(account_id, mas_session_id, workflow_version),
        "legacy_compat": dict(legacy_compat["legacy_compat"]),
    }
