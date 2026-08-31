"""Generation-keyed summary storage with recoverable, side-effect-free generation."""
import time
from hashlib import sha256
from uuid import uuid4

from mas_memory_store import update_json


def build_summary(data, generate, export=None):
    patient = data.get("patient_id")
    generation = data.get("session_generation")
    history = data.get("chat_history")
    if not isinstance(patient, str) or not patient or type(generation) is not int or generation < 1 or not isinstance(history, list):
        raise ValueError("invalid_summary_identity")
    key = "adaptive_summary_" + sha256(f"{patient}:{generation}".encode()).hexdigest()[:40]
    token, now = uuid4().hex, time.time()
    def claim(old):
        if old and old.get("status") == "completed":
            return old
        if old and old.get("lease_until", 0) > now:
            return old
        return {"status": "processing", "token": token, "lease_until": now + 180,
            "patient_id": patient, "session_generation": generation}
    state = update_json("ssa", key, claim)
    if state["status"] == "completed":
        return {"status": "ok", "summary": state["summary"], "replayed": True,
            "memory_export_status": export_once(key, data, export) if export else "not_requested"}
    if state["token"] != token:
        return {"status": "processing"}
    try:
        summary = generate(history, data.get("review_outcome", "reviewed"))
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("empty_summary")
        # A single CAS append makes retries/restarts safe even between the two writes.
        def append(items):
            items = items or []
            if not any(item.get("summary_id") == key for item in items):
                items.append({"summary_id": key, "patient_id": patient,
                    "session_generation": generation, "chat_history": history,
                    "review_outcome": data.get("review_outcome"), "summary": summary})
            return items
        items = update_json("ssa", "session_summaries", append)
        summary = next(item["summary"] for item in items if item.get("summary_id") == key)
        def finish(current):
            if current.get("token") != token:
                return current
            return {**current, "status": "completed", "summary": summary, "lease_until": 0}
        state = update_json("ssa", key, finish)
        if state["status"] == "completed":
            return {"status": "ok", "summary": summary,
                "memory_export_status": export_once(key, data, export) if export else "not_requested"}
        return {"status": "processing"}
    except Exception:
        def release(current):
            if current.get("token") == token:
                current["lease_until"] = 0
            return current
        update_json("ssa", key, release)
        raise


def export_once(key, data, export):
    """MMA's existing extract is non-idempotent: never retry an uncertain write."""
    token = uuid4().hex
    def claim(state):
        if state.get("memory_export_status"):
            return state
        state.update(memory_export_status="indeterminate", export_token=token)
        return state
    state = update_json("ssa", key, claim)
    if state.get("export_token") != token:
        return state["memory_export_status"]
    try:
        export(data)
        outcome = "completed"
    except Exception:
        outcome = "indeterminate"
    update_json("ssa", key, lambda state: {**state, "memory_export_status": outcome})
    return outcome
