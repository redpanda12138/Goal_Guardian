from threading import Lock
from uuid import uuid4

from runtime_config import langgraph_new_sessions_enabled
from workflow_phase1.contracts import RouteDecision
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


def workflow_projection(record):
    """Return the explicit graph phase/stage without mutating durable state."""
    if session_identity(record)["workflow_mode"] != GRAPH_MODE:
        return {}

    turn_index = int(record.get("turn_index", 0))
    reservations = record.get("graph_transition_reservations") or {}
    active_agent = None
    for reservation in reversed(list(reservations.values())):
        if reservation.get("status") in {"reserved", "dispatching"}:
            active_agent = reservation.get("agent")
            break

    if active_agent == "SSA" or turn_index >= 15:
        phase = "summary"
    elif active_agent == "SCA" or turn_index == 14:
        phase = "closing"
    elif active_agent == "GRA" or turn_index >= 6:
        phase = "review_decision"
    else:
        phase = "opening"

    history = record.get("chat_history") or []
    waiting_for_user = (
        active_agent is None
        and turn_index < 15
        and bool(history)
        and history[-1].get("role") == "assistant"
    )
    return {
        "workflow_phase": phase,
        "workflow_stage": "waiting_user" if waiting_for_user else phase,
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


def reset_patient_session(load_records, save_records, patient_id):
    with _reservation_lock:
        records = load_records()
        record = next((item for item in records if item.get("patient_id") == patient_id), None)
        if record is None:
            record = {"patient_id": patient_id}
            records.append(record)
        reset_and_latch(record)
        save_records(records)
        return dict(record)


def reset_active_sessions(load_records, save_records):
    with _reservation_lock:
        records = load_records()
        reset_count = 0
        for record in records:
            if record.get("turn_index", 0) > 0 or record.get("chat_history"):
                reset_and_latch(record)
                reset_count += 1
        if reset_count:
            save_records(records)
        return reset_count


def reserve_graph_dispatch(load_records, save_records, patient_id, generation, request_id, turn_index, event_type="user_turn", requested_agent=None, user_input=None):
    with _reservation_lock:
        # Reload and persist under one process-local critical section. Callers must
        # not supply snapshots: two requests that started with stale data still
        # serialize against the latest durable OA document.
        records = load_records()
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
            return RouteDecision(prior["agent"], "existing_reservation", "ready"), prior["status"]
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
            return decision, "session_completed"
        reservations[request_id] = {"status": "reserved", "agent": decision.selected_agent}
        if user_input is not None:
            record.setdefault("chat_history", []).append({"role": "user", "content": user_input})
        save_records(records)
        return decision, "reserved"


def transition_dispatch(load_records, save_records, patient_id, request_id, expected, target):
    with _reservation_lock:
        records = load_records()
        record = next(item for item in records if item.get("patient_id") == patient_id)
        reservation = record["graph_transition_reservations"][request_id]
        if reservation["status"] != expected:
            return False, reservation["status"]
        reservation["status"] = target
        save_records(records)
        return True, target


def new_request_id():
    return uuid4().hex
