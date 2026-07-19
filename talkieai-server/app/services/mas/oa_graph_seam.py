from uuid import NAMESPACE_URL, uuid5

from app.config import Config
from app.services.mas.rag_retrieval import validate_retrieval_trace


class OAGraphRoutingError(RuntimeError):
    pass


def stable_graph_request_id(account_id, session_id, message_id):
    if not all(isinstance(value, str) and value for value in (account_id, session_id, message_id)):
        raise ValueError("stable graph request identity is required")
    return uuid5(NAMESPACE_URL, f"goalguardian:{account_id}:{session_id}:{message_id}").hex


async def route_if_latched_graph(gateway, patient_id, user_input, turn_index, request_id):
    if not Config.MAS_OA_GRAPH_SEAM_ENABLED:
        return None
    mode = await gateway.call_mas_service("oa", f"/workflow_mode/{patient_id}", method="GET")
    if not isinstance(mode, dict) or mode.get("status") != "ok":
        raise OAGraphRoutingError("ambiguous OA workflow mode response")
    workflow_mode = mode.get("workflow_mode")
    if workflow_mode == "legacy":
        return None
    if workflow_mode != "graph_v1" or mode.get("workflow_version") != "oa_graph_v1" or type(mode.get("session_generation")) is not int:
        raise OAGraphRoutingError("invalid OA graph session identity")
    result = await gateway.call_mas_service("oa", "/graph_v1/user_turn", data={
        "patient_id": patient_id,
        "user_input": user_input,
        "turn_index": turn_index,
        "request_id": request_id,
        "session_generation": mode["session_generation"],
    })
    if not isinstance(result, dict) or result.get("status") not in {"ok", "completed", "tool_requested"}:
        raise OAGraphRoutingError("OA graph ingress failed closed")
    if result.get("retrieval_results") is not None:
        try:
            result["retrieval_results"] = validate_retrieval_trace(
                result["retrieval_results"]
            )
        except ValueError as error:
            raise OAGraphRoutingError("OA returned an invalid retrieval trace") from error
    return result
