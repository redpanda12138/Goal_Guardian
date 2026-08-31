"""Application-side contracts for OA-owned adaptive sessions."""


def is_completed(status):
    if status.get("workflow_mode") == "adaptive_v1":
        return status.get("session_status") == "completed"
    return status.get("session_status") == "completed" or status.get("turn_index", 0) >= 15


async def notify_tool(gateway, patient_id, identity, status, result=None):
    if identity.get("workflow_mode") != "adaptive_v1" or identity.get("workflow_version") != "oa_adaptive_v1":
        raise ValueError("invalid adaptive tool identity")
    response = await gateway.call_mas_service("oa", "/adaptive_v1/tool_event", data={
        "patient_id": patient_id, "session_generation": identity["session_generation"],
        "operation_id": identity["operation_id"], "action_status": status, "tool_result": result,
    })
    if not isinstance(response, dict) or response.get("status") != "ok":
        raise RuntimeError("OA did not acknowledge the tool event")
    return response


async def start_if_adaptive(gateway, patient_id):
    from app.config import Config
    if not Config.MAS_OA_GRAPH_SEAM_ENABLED:
        return None
    mode = await gateway.call_mas_service("oa", f"/workflow_mode/{patient_id}", method="GET")
    if not isinstance(mode, dict) or mode.get("status") != "ok":
        raise RuntimeError("OA workflow mode is unavailable")
    if mode.get("workflow_mode") != "adaptive_v1":
        return None
    return await gateway.call_mas_service("oa", "/adaptive_v1/start", data={"patient_id": patient_id})


async def resolve_adaptive_action(db, account_id, store, action, confirmed, gateway, patient_id, execute):
    from fastapi import HTTPException
    from app.models.mas_workflow_models import ToolRequest, ToolResult, ToolResultStatus
    identity = action["workflow_identity"]
    if not confirmed:
        await notify_tool(gateway, patient_id, identity, "cancelled")
        cancelled = action if action["status"] == "cancelled" else store.cancel(action["action_id"], account_id)
        db.commit()
        return {"action_id": action["action_id"], "action_status": cancelled["status"]}
    if action["status"] in {"completed", "failed"}:
        request = ToolRequest.parse_obj(action["tool_request"])
        result = ToolResult(tool_name=request.tool_name,
            status=ToolResultStatus.SUCCEEDED if action["status"] == "completed" else ToolResultStatus.FAILED,
            payload={"replayed_terminal_result": True})
        finished = action
    else:
        try:
            await notify_tool(gateway, patient_id, identity, "executing")
        except Exception as error:
            raise HTTPException(409, "The action is not executable in the current workflow") from error
        request = store.claim(action["action_id"], account_id)
        db.commit()
        result = await execute(db, account_id, request, confirmed=True)
        finished = store.finish(action["action_id"], account_id, result.status.value)
        db.commit()
    data = {**result.dict(), "action_id": action["action_id"], "action_status": finished["status"]}
    try:
        response = await notify_tool(gateway, patient_id, identity, result.status.value, result.dict())
        data.update({key: response.get(key) for key in ("assistant_message", "session_status", "stage_count")})
    except Exception:
        # The write is already terminal. Never tell the user to repeat it.
        data.update(assistant_message="", continuation_pending=True)
    return data


async def reconcile_terminal_tools(db, account_id, gateway, patient_id, generation):
    from app.services.mas.pending_tool_confirmation import PendingToolConfirmationStore
    store = PendingToolConfirmationStore(db)
    rows = db.query(store.entity_model).filter(
        store.entity_model.account_id == account_id,
        store.entity_model.status.in_(["completed", "failed", "cancelled"]),
    ).all()
    for row in rows:
        action = store._serialize(row)
        identity = action.get("workflow_identity")
        if not identity or identity.get("session_generation") != generation:
            continue
        status = "succeeded" if action["status"] == "completed" else action["status"]
        await notify_tool(gateway, patient_id, identity, status)
