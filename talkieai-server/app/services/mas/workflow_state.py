"""JSON-only checkpoint state helpers for the future MAS workflow."""
import re
from typing import Any, Dict

from app.services.mas.workflow_identity import derive_thread_id, validate_stable_identifier
from app.services.mas.workflow_json import ensure_json_object


WORKFLOW_VERSION_PATTERN = r"^v[1-9][0-9]*$"
LEGACY_SESSION_STATUSES = {"active", "completed"}


class LegacyCompatStateAdapter:
    """Expose only recoverable legacy facts under the legacy_compat namespace."""

    @staticmethod
    def bootstrap(
        legacy_turn_index: int, legacy_session_status: str
    ) -> Dict[str, Dict[str, Any]]:
        if (
            isinstance(legacy_turn_index, bool)
            or not isinstance(legacy_turn_index, int)
            or not 0 <= legacy_turn_index <= 15
        ):
            raise ValueError("legacy_turn_index must be an integer between 0 and 15")
        if legacy_session_status not in LEGACY_SESSION_STATUSES:
            raise ValueError("legacy_session_status must be active or completed")
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
    validate_stable_identifier(mas_session_id, "mas_session_id")
    validate_stable_identifier(request_id, "request_id")
    if not isinstance(workflow_version, str) or not re.fullmatch(
        WORKFLOW_VERSION_PATTERN, workflow_version
    ):
        raise ValueError("workflow_version must be a version such as v1")
    if not isinstance(legacy_compat, dict) or set(legacy_compat) != {"legacy_compat"}:
        raise ValueError("legacy adapters may only provide legacy_compat")
    legacy_data = legacy_compat["legacy_compat"]
    if not isinstance(legacy_data, dict) or set(legacy_data) != {
        "legacy_turn_index",
        "legacy_session_status",
    }:
        raise ValueError("legacy_compat must contain only validated legacy session facts")
    validated_legacy = LegacyCompatStateAdapter.bootstrap(
        legacy_data["legacy_turn_index"], legacy_data["legacy_session_status"]
    )
    state = {
        "state_version": "v1",
        "workflow_version": workflow_version,
        "account_id": account_id,
        "mas_session_id": mas_session_id,
        "request_id": request_id,
        "thread_id": derive_thread_id(account_id, mas_session_id, workflow_version),
        "legacy_compat": validated_legacy["legacy_compat"],
    }
    return ensure_json_object(state)
