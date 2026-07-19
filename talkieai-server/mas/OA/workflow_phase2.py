from threading import Lock
from uuid import uuid4

from runtime_config import langgraph_new_sessions_enabled
from workflow_phase1.graph import invoke_phase1_graph

LEGACY_MODE = "legacy"
GRAPH_MODE = "graph_v1"
GRAPH_VERSION = "oa_graph_v1"
_reservation_lock = Lock()


def session_identity(record):
    return {
        "workflow_mode": record.get("workflow_mode", LEGACY_MODE),
        "workflow_version": record.get("workflow_version", "legacy"),
        "session_generation": int(record.get("session_generation", 1)),
    }


def reset_and_latch(record):
    generation = int(record.get("session_generation", 0)) + 1
    mode = GRAPH_MODE if langgraph_new_sessions_enabled() else LEGACY_MODE
    record.update({
        "turn_index": 0,
        "chat_history": [],
        "workflow_mode": mode,
        "workflow_version": GRAPH_VERSION if mode == GRAPH_MODE else "legacy",
        "session_generation": generation,
        "graph_transition_reservations": {},
    })
    return record


def reserve_graph_dispatch(records, patient_id, generation, request_id, turn_index, event_type="user_turn", requested_agent=None):
    with _reservation_lock:
        record = next((item for item in records if item.get("patient_id") == patient_id), None)
        if record is None:
            raise ValueError("session_not_found")
        identity = session_identity(record)
        if identity["workflow_mode"] != GRAPH_MODE:
            raise ValueError("not_graph_session")
        if generation != identity["session_generation"]:
            raise ValueError("stale_session_generation")
        reservations = record.setdefault("graph_transition_reservations", {})
        prior = reservations.get(request_id)
        if prior:
            return None, prior["status"]
        decision = invoke_phase1_graph({
            "patient_id": patient_id,
            "session_generation": generation,
            "workflow_version": identity["workflow_version"],
            "request_id": request_id,
            "event_type": event_type,
            "turn_index": turn_index,
            "session_status": "completed" if turn_index == 15 else "active",
            **({"requested_agent": requested_agent} if requested_agent else {}),
        })
        if decision.route_status == "error":
            return decision, "conflict"
        if decision.selected_agent is None:
            return decision, "completed"
        reservations[request_id] = {"status": "reserved", "agent": decision.selected_agent}
        return decision, "reserved"


def mark_dispatched(records, patient_id, request_id):
    with _reservation_lock:
        record = next(item for item in records if item.get("patient_id") == patient_id)
        reservation = record["graph_transition_reservations"][request_id]
        reservation["status"] = "dispatched"


def new_request_id():
    return uuid4().hex
