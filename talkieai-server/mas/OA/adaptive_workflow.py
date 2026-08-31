"""Durable OA stage machine. Model services return data and never mutate it."""
from hashlib import sha256
import time

from adaptive_policy import MODE, VERSION, DEFAULT_RANGES, assess_transition, stage_range
from mas_memory_store import load_json, update_json
from tool_catalog import valid_adaptive_tool_call


def identity(state):
    return {key: state[key] for key in ("workflow_mode", "workflow_version", "session_generation")}


def projection(state):
    phase = {"SOA": "opening", "GRA": "review_decision", "SCA": "closing", "SSA": "summary"}[state["active_agent"]]
    return {
        **identity(state), "session_status": state["session_status"],
        "current_agent": state["active_agent"], "stage_count": state["stage_count"],
        "turn_index": state["turn_index"], "workflow_phase": phase,
        "workflow_stage": "paused" if state["session_status"] == "paused" else phase,
        "revision": state["revision"], "review_outcome": state["review_outcome"],
        "recovery_requested": state["recovery_requested"],
        "stop_requested": state["stop_requested"], "summary_status": state["summary_status"],
    }


class AdaptiveWorkflow:
    def __init__(self, patient_id):
        if not isinstance(patient_id, str) or not patient_id:
            raise ValueError("patient_id_required")
        self.patient_id = patient_id
        self.document = "adaptive_" + sha256(patient_id.encode()).hexdigest()[:40]

    def get(self):
        return load_json("oa", self.document, None)

    def update(self, transform):
        return update_json("oa", self.document, transform)

    def reset(self, initialize_only=False):
        def reset(old):
            if initialize_only and old is not None:
                return old
            if old and any(a["status"] == "executing" for a in old["actions"].values()):
                raise ValueError("action_still_executing")
            return {
                "patient_id": self.patient_id, "workflow_mode": MODE, "workflow_version": VERSION,
                "session_generation": (old or {}).get("session_generation", 0) + 1,
                "revision": (old or {}).get("revision", 0) + 1,
                "active_agent": "SOA", "stage_count": 0, "turn_index": 0,
                "session_status": "active", "review_outcome": "in_progress",
                "chat_history": [], "requests": {}, "actions": {}, "decisions": [],
                "inflight": None, "recovery_requested": False, "extension_used": False,
                "assessment_failures": 0, "stop_requested": False,
                "ranges": {stage: list(stage_range(stage)) for stage in DEFAULT_RANGES},
                "summary_status": "not_requested",
            }
        return self.update(reset)

    @staticmethod
    def check_generation(state, generation):
        if not state or type(generation) is not int or generation != state["session_generation"]:
            raise ValueError("stale_session_generation")
        if state.get("workflow_version") != VERSION or state.get("workflow_mode") != MODE:
            raise ValueError("workflow_version_mismatch")

    def accept(self, request_id, text, generation):
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 160:
            raise ValueError("invalid_request_id")
        if not isinstance(text, str) or not text.strip() or len(text) > 16000:
            raise ValueError("invalid_user_input")

        def accept(state):
            self.check_generation(state, generation)
            prior = state["requests"].get(request_id)
            if prior:
                if prior["input"] != text:
                    raise ValueError("request_conflict")
                return state
            reserved = {request_id + suffix for suffix in ("", ":reply", ":tool-result", ":confirmation")}
            if reserved & {message["id"] for message in state["chat_history"]}:
                raise ValueError("message_id_conflict")
            if state["inflight"]:
                raise ValueError("turn_in_progress")
            if state["session_status"] != "active":
                raise ValueError("session_" + state["session_status"])
            if state["recovery_requested"]:
                raise ValueError("recovery_choice_required")
            if any(item["status"] in {"pending", "executing"} for item in state["actions"].values()):
                raise ValueError("pending_action")
            state["revision"] += 1
            state["turn_index"] += 1
            state["stage_count"] += 1
            state["inflight"] = request_id
            state["chat_history"].append({"id": request_id, "role": "user", "content": text})
            state["requests"][request_id] = {"input": text, "status": "processing", "response": None}
            return state
        return self.update(accept)

    def finish(self, request_id, revision, output):
        def finish(state):
            if not state or state["revision"] != revision or state["inflight"] != request_id:
                raise ValueError("stale_state")
            stage = state["active_agent"]
            knowledge_turn = stage == "GRA" and output.get("turn_kind") == "knowledge"
            if knowledge_turn:
                # A side question remains in the transcript but is not a review
                # response, a completion signal, or permission to execute tools.
                state["stage_count"] = max(0, state["stage_count"] - 1)
                for msg in state["chat_history"]:
                    if msg["id"] == request_id:
                        msg["review_evidence"] = False
            model_message = output.get("model_message") or {}
            if not isinstance(model_message, dict):
                model_message = {}
            if knowledge_turn:
                model_message = {}
            if valid_adaptive_tool_call(stage, model_message.get("tool_calls")):
                state["actions"][request_id] = {"status": "pending", "result": None}
                response = {"status": "tool_requested", "model_message": model_message,
                            "workflow_identity": {**identity(state), "operation_id": request_id}}
            else:
                assessment = output.get("assessment")
                decision = ({"next_agent": stage, "reason": "knowledge_turn", "needs_recovery": False}
                    if knowledge_turn else assess_transition(stage, state["stage_count"], assessment,
                    {msg["id"] for msg in state["chat_history"] if msg.get("review_evidence") is not False},
                    bounds=state["ranges"][stage]))
                message = output.get("assistant_message")
                if not isinstance(message, str) or not message.strip():
                    message = "Could you clarify that before the review continues?"
                if not knowledge_turn and decision["next_agent"] == stage and isinstance(assessment, dict) and assessment.get("decision") == "advance":
                    message = {"SOA": "Before reviewing your goal, could you tell me more about how you are feeling and whether you are ready?",
                        "GRA": "Before summarising, could you clarify your progress, any barriers, and your next step?",
                        "SCA": "Is the recap accurate, and are you ready to end this review?"}[stage]
                if model_message.get("tool_calls"):
                    message = "The requested action could not be prepared. Please clarify what you would like to do."
                if decision["reason"] == "invalid_assessment":
                    state["assessment_failures"] += 1
                    message = "The review could not assess that response. Please clarify or pause the session."
                else:
                    state["assessment_failures"] = 0
                state["decisions"].append({"request_id": request_id, "stage": stage,
                    "stage_count": state["stage_count"], "assessment": assessment, **decision})
                if decision["next_agent"] != stage:
                    state["active_agent"] = decision["next_agent"]
                    state["stage_count"] = 0
                    state["recovery_requested"] = False
                    state["extension_used"] = False
                    if state["active_agent"] == "SSA":
                        state["session_status"] = "completed"
                        if state["review_outcome"] != "skipped":
                            state["review_outcome"] = "reviewed"
                        state["summary_status"] = "pending"
                elif state["assessment_failures"] >= 2 or (decision["needs_recovery"] and state["extension_used"]):
                    state["session_status"] = "paused"
                    message = "The review is paused with your progress saved. Resume when you are ready."
                elif decision["needs_recovery"]:
                    state["recovery_requested"] = True
                    message = "There are still review items to discuss. Continue for two more responses, or pause?"
                grounded_message = output.get("assistant_message")
                if (output.get("turn_kind") == "mixed_review" and isinstance(grounded_message, str)
                    and grounded_message.strip() and message != grounded_message):
                    message = grounded_message + "\n\n" + message
                message = message[:2400]
                reply_record = {"id": request_id + ":reply", "role": "assistant", "content": message}
                if knowledge_turn or output.get("turn_kind") == "mixed_review":
                    reply_record["review_evidence"] = False
                state["chat_history"].append(reply_record)
                response = {"status": "ok", "assistant_message": message, "persisted": True}
                if knowledge_turn or output.get("turn_kind") == "mixed_review":
                    response.update(turn_kind=output["turn_kind"], grounding=output.get("grounding", {}))
            state["inflight"] = None
            state["revision"] += 1
            response.update(projection(state))
            response["request_id"] = request_id
            response["retrieval_results"] = output.get("retrieval_results", [])
            state["requests"][request_id].update(status="completed", response=response)
            return state
        state = self.update(finish)
        return state["requests"][request_id]["response"]

    def claim_dispatch(self, request_id, generation, now=None):
        now = time.time() if now is None else now
        def claim(state):
            self.check_generation(state, generation)
            prior = state["requests"].get(request_id)
            if not prior or state["inflight"] != request_id:
                raise ValueError("turn_interrupted")
            if prior["status"] == "dispatching" and prior.get("lease_until", 0) > now:
                raise ValueError("turn_in_progress")
            if prior["status"] not in {"processing", "dispatching"}:
                raise ValueError("turn_interrupted")
            prior.update(status="dispatching", lease_until=now + 180)
            state["revision"] += 1
            return state
        return self.update(claim)

    def control(self, command, generation):
        if command not in {"pause", "resume", "extend", "stop", "skip"}:
            raise ValueError("invalid_control")

        def control(state):
            self.check_generation(state, generation)
            if state["session_status"] == "completed":
                raise ValueError("session_completed")
            if state["inflight"] and command not in {"pause", "stop"}:
                raise ValueError("turn_in_progress")
            if command in {"resume", "extend"}:
                if state["stop_requested"]:
                    raise ValueError("session_stopping")
                if command == "extend" and (not state["recovery_requested"] or state["extension_used"]):
                    raise ValueError("extension_unavailable")
                if command == "resume" and state["session_status"] != "paused":
                    raise ValueError("session_not_paused")
                state["session_status"] = "active"
                stage = state["active_agent"]
                if command == "extend" or state["stage_count"] >= state["ranges"][stage][2] or state["recovery_requested"]:
                    state["ranges"][stage][2] = max(state["ranges"][stage][1], state["stage_count"] + 2)
                    state["extension_used"] = True
                state["recovery_requested"] = False
                state["assessment_failures"] = 0
            elif command == "skip":
                if state["inflight"] or any(a["status"] in {"pending", "executing"} for a in state["actions"].values()):
                    raise ValueError("pending_action")
                if state["active_agent"] not in {"SOA", "GRA"}:
                    raise ValueError("review_already_closed")
                state["review_outcome"] = "skipped"
                state["active_agent"] = "SCA"
                state["stage_count"] = 0
                state["recovery_requested"] = False
                state["extension_used"] = False
            else:
                state["session_status"] = "paused"
                if state["inflight"]:
                    state["requests"][state["inflight"]]["status"] = "interrupted"
                    state["inflight"] = None
                if command == "stop":
                    state["stop_requested"] = True
                    state["review_outcome"] = "stopped"
                    for action in state["actions"].values():
                        if action["status"] == "pending":
                            action["status"] = "cancelled"
                    if not any(a["status"] == "executing" for a in state["actions"].values()):
                        state["session_status"] = "completed"
                        state["summary_status"] = "pending"
            state["revision"] += 1
            return state
        return self.update(control)

    def tool_event(self, operation_id, status, generation, result=None):
        allowed = {"executing", "succeeded", "failed", "cancelled"}
        if status not in allowed:
            raise ValueError("invalid_tool_status")

        def apply(state):
            self.check_generation(state, generation)
            action = state["actions"].get(operation_id)
            if not action:
                raise ValueError("unknown_action")
            if action["status"] == status:
                return state
            permitted = {"pending": allowed, "executing": {"succeeded", "failed"}}
            if status not in permitted.get(action["status"], set()):
                raise ValueError("action_already_resolved")
            action.update(status=status, result=result)
            if status in {"succeeded", "failed", "cancelled"}:
                message = {"succeeded": "The action completed successfully.",
                           "failed": "The action could not be completed.",
                           "cancelled": "The action was cancelled without writing data."}[status]
                if status == "succeeded" and isinstance(result, dict) and result.get("tool_name") == "get_weekly_progress":
                    payload = result.get("payload") or {}
                    progress = payload.get("weekly_progress", {}) if isinstance(payload, dict) else {}
                    completed, total = progress.get("completed"), progress.get("total")
                    if type(completed) is int and type(total) is int and 0 <= completed <= total:
                        message = f"Your weekly progress shows {completed} of {total} goals completed."
                    else:
                        message = "The weekly progress totals are currently unavailable."
                state["chat_history"].append({"id": operation_id + ":tool-result", "role": "assistant", "content": message})
            if state["stop_requested"] and not any(a["status"] == "executing" for a in state["actions"].values()):
                state["session_status"] = "completed"
                state["summary_status"] = "pending"
            state["revision"] += 1
            return state
        return self.update(apply)

    def append_tool_message(self, operation_id, generation, message):
        if not isinstance(message, str) or not message.strip() or len(message) > 16000:
            raise ValueError("invalid_tool_message")

        def apply(state):
            self.check_generation(state, generation)
            if operation_id not in state["actions"]:
                raise ValueError("unknown_action")
            message_id = operation_id + ":confirmation"
            if not any(m["id"] == message_id for m in state["chat_history"]):
                if state["session_status"] != "active" or state["actions"][operation_id]["status"] != "pending":
                    raise ValueError("action_not_pending")
                state["chat_history"].append({"id": message_id, "role": "assistant", "content": message})
                state["revision"] += 1
            return state
        return self.update(apply)
