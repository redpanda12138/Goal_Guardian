"""Database-backed lifecycle for model-proposed write-tool confirmations."""

import json
from typing import Any, Dict, Optional, Type

from pydantic import ValidationError

from app.core.utils import short_uuid
from app.db.mas_entities import WorkflowToolConfirmationEntity
from app.models.mas_workflow_models import ToolRequest
from app.services.mas.tool_executor import WRITE_TOOLS


class PendingActionNotFound(LookupError):
    pass


class PendingActionConflict(RuntimeError):
    pass


class PendingToolConfirmationStore:
    def __init__(
        self,
        db: Any,
        entity_model: Type[WorkflowToolConfirmationEntity] = WorkflowToolConfirmationEntity,
    ) -> None:
        self.db = db
        self.entity_model = entity_model

    def create(
        self,
        account_id: str,
        session_id: str,
        message_id: str,
        turn_index: int,
        request: ToolRequest,
        workflow_identity: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if request.tool_name not in WRITE_TOOLS or request.requires_confirmation is not True:
            raise ValueError("only confirmation-gated write tools may be persisted")
        if type(turn_index) is not int or turn_index < 0:
            raise ValueError("turn_index must be a non-negative integer")
        if not all(
            isinstance(value, str) and value
            for value in (account_id, session_id, message_id)
        ):
            raise ValueError("stable action ownership identifiers are required")

        request_json = request.json()
        if workflow_identity is not None:
            if (workflow_identity.get("workflow_mode") != "adaptive_v1"
                    or workflow_identity.get("workflow_version") != "oa_adaptive_v1"
                    or type(workflow_identity.get("session_generation")) is not int
                    or workflow_identity["session_generation"] < 1
                    or not isinstance(workflow_identity.get("operation_id"), str)
                    or not workflow_identity["operation_id"]):
                raise ValueError("invalid adaptive action identity")
            request_json = json.dumps({"tool_request": json.loads(request_json), "workflow_identity": workflow_identity})
        entity = self.entity_model(
            action_id=short_uuid(),
            account_id=account_id,
            session_id=session_id,
            message_id=message_id,
            turn_index=turn_index,
            tool_request_json=request_json,
            status="pending",
        )
        self.db.add(entity)
        self.db.flush()
        return self._serialize(entity)

    def get_for_message(
        self, message_id: str, account_id: str
    ) -> Optional[Dict[str, Any]]:
        entity = (
            self.db.query(self.entity_model)
            .filter_by(message_id=message_id, account_id=account_id)
            .first()
        )
        return self._serialize(entity) if entity is not None else None

    def get(self, action_id: str, account_id: str) -> Dict[str, Any]:
        return self._serialize(self._owned_action(action_id, account_id, lock=False))

    def has_blocking_for_session(self, session_id: str, account_id: str) -> bool:
        return (
            self.db.query(self.entity_model)
            .filter(
                self.entity_model.session_id == session_id,
                self.entity_model.account_id == account_id,
                self.entity_model.status.in_(["pending", "executing"]),
            )
            .first()
            is not None
        )

    def claim(self, action_id: str, account_id: str) -> ToolRequest:
        entity = self._owned_action(action_id, account_id, lock=True)
        if entity.status != "pending":
            raise PendingActionConflict("pending action is no longer executable")
        request = self._parse_request(entity.tool_request_json)
        entity.status = "executing"
        self.db.flush()
        return request

    def cancel(self, action_id: str, account_id: str) -> Dict[str, Any]:
        entity = self._owned_action(action_id, account_id, lock=True)
        if entity.status != "pending":
            raise PendingActionConflict("pending action is no longer cancellable")
        entity.status = "cancelled"
        self.db.flush()
        return self._serialize(entity)

    def finish(
        self, action_id: str, account_id: str, tool_status: str
    ) -> Dict[str, Any]:
        entity = self._owned_action(action_id, account_id, lock=True)
        if entity.status != "executing":
            raise PendingActionConflict("pending action is not executing")
        if tool_status not in {"succeeded", "failed"}:
            raise ValueError("tool_status must be succeeded or failed")
        entity.status = "completed" if tool_status == "succeeded" else "failed"
        self.db.flush()
        return self._serialize(entity)

    def _owned_action(self, action_id: str, account_id: str, *, lock: bool):
        query = self.db.query(self.entity_model).filter_by(
            action_id=action_id, account_id=account_id
        )
        if lock:
            query = query.with_for_update()
        entity = query.first()
        if entity is None:
            raise PendingActionNotFound("pending action was not found")
        return entity

    @staticmethod
    def _parse_request(raw: str) -> ToolRequest:
        try:
            payload = json.loads(raw)
            return ToolRequest.parse_obj(payload.get("tool_request", payload))
        except (ValidationError, ValueError, TypeError) as error:
            raise PendingActionConflict("stored tool request is invalid") from error

    def _serialize(self, entity: Any) -> Dict[str, Any]:
        request = self._parse_request(entity.tool_request_json)
        result = {
            "action_id": entity.action_id,
            "tool_request": json.loads(request.json()),
            "turn_index": entity.turn_index,
            "status": entity.status,
        }
        envelope = json.loads(entity.tool_request_json)
        if "workflow_identity" in envelope:
            result["workflow_identity"] = envelope["workflow_identity"]
            result["session_id"] = entity.session_id
        return result
