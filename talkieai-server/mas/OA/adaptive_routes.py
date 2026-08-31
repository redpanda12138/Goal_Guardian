"""OA-owned adaptive ingress; remote agent calls happen outside transactions."""
import asyncio
import os
import time
from uuid import uuid4

import requests
from fastapi import APIRouter, HTTPException, Request

from adaptive_policy import MODE
from adaptive_workflow import AdaptiveWorkflow, projection

router = APIRouter(prefix="/adaptive_v1")


def enabled():
    return os.getenv("OA_ADAPTIVE_ENABLED", "false").lower() == "true"


def existing(patient_id):
    return AdaptiveWorkflow(patient_id).get() if patient_id else None


def start_session(patient_id):
    workflow = AdaptiveWorkflow(patient_id)
    if not workflow.get():
        if not enabled():
            raise ValueError("adaptive_disabled")
        workflow.reset(initialize_only=True)
    def greet(state):
        if not state["chat_history"]:
            state["chat_history"].append({"id": "opening", "role": "assistant",
                "content": "Hello! How are you feeling today, and are you ready to review your weekly goal?"})
            state["revision"] += 1
        return state
    state = workflow.update(greet)
    return {"status": "ok", "assistant_message": state["chat_history"][0]["content"],
            "persisted": True, **projection(state)}


def dispatch_stage(state):
    context = {"tool_results": [{"operation_id": key, **action} for key, action in state["actions"].items()
        if action["status"] in {"succeeded", "failed", "cancelled"}][-10:]}
    for field, endpoint in (("goals", "patient_goals"), ("personal_context", "patient_notes")):
        try:
            response = requests.get(f"http://mma:8000/{endpoint}/{state['patient_id']}", timeout=(3, 10))
            response.raise_for_status()
            context[field] = response.json()
        except (requests.RequestException, ValueError):
            context[field] = {"unavailable": True}
    payload = {key: state[key] for key in ("patient_id", "active_agent", "stage_count", "ranges", "chat_history")}
    response = requests.post(f"http://{state['active_agent'].lower()}:8000/adaptive_reply",
        json={**payload, "context": context}, timeout=(3, 120))
    response.raise_for_status()
    output = response.json()
    if not isinstance(output, dict):
        raise ValueError("invalid_agent_response")
    return output


def summarise_if_ready(workflow):
    state = workflow.get()
    if not state or state["summary_status"] in {"not_requested", "completed"}:
        return
    generation = state["session_generation"]
    now, token = time.time(), uuid4().hex
    def claim(current):
        workflow.check_generation(current, generation)
        if current["summary_status"] == "completed" or current.get("summary_lease_until", 0) > now:
            raise ValueError("summary_already_claimed")
        current["summary_status"] = "processing"
        current["summary_lease_until"] = now + 180
        current["summary_token"] = token
        current["revision"] += 1
        return current
    try:
        state = workflow.update(claim)
    except ValueError:
        return
    outcome = "completed"
    try:
        response = requests.post("http://ssa:8000/adaptive_summary", json={
            "patient_id": state["patient_id"], "chat_history": state["chat_history"],
            "session_generation": generation, "review_outcome": state["review_outcome"],
        }, timeout=(3, 120))
        response.raise_for_status()
        if response.json().get("status") != "ok":
            outcome = "failed"
    except (requests.RequestException, ValueError):
        outcome = "indeterminate"
    def finish(current):
        workflow.check_generation(current, generation)
        if current.get("summary_token") != token:
            return current
        current["summary_status"] = outcome
        current["summary_lease_until"] = time.time() + 30 if outcome != "completed" else 0
        current["revision"] += 1
        return current
    try:
        workflow.update(finish)
    except ValueError:
        pass  # A new session must not receive an older summary's status.


@router.post("/start")
async def start(request: Request):
    data = await request.json()
    try:
        return await asyncio.to_thread(start_session, data.get("patient_id"))
    except ValueError as error:
        raise HTTPException(409, str(error))


@router.post("/user_turn")
async def user_turn(request: Request):
    data = await request.json()
    try:
        workflow = AdaptiveWorkflow(data.get("patient_id"))
        request_id = data.get("request_id")
        state = await asyncio.to_thread(workflow.accept, request_id, data.get("user_input"), data.get("session_generation"))
        prior = state["requests"][request_id]
        if prior["response"] is not None:
            if state["session_status"] == "completed":
                await asyncio.to_thread(summarise_if_ready, workflow)
            return prior["response"]
        state = await asyncio.to_thread(workflow.claim_dispatch, request_id, data.get("session_generation"))
        try:
            output = await asyncio.to_thread(dispatch_stage, state)
        except Exception:
            output = {"assessment": None}
        result = await asyncio.to_thread(workflow.finish, request_id, state["revision"], output)
        if result["session_status"] == "completed":
            await asyncio.to_thread(summarise_if_ready, workflow)
        return result
    except ValueError as error:
        raise HTTPException(409, str(error))


@router.post("/control")
async def control(request: Request):
    data = await request.json()
    try:
        workflow = AdaptiveWorkflow(data.get("patient_id"))
        state = await asyncio.to_thread(workflow.control, data.get("command"), data.get("session_generation"))
        if state["session_status"] == "completed":
            await asyncio.to_thread(summarise_if_ready, workflow)
        return {"status": "ok", **projection(state),
                "cancelled_operations": [key for key, action in state["actions"].items() if action["status"] == "cancelled"]}
    except ValueError as error:
        raise HTTPException(409, str(error))


@router.post("/tool_event")
async def tool_event(request: Request):
    data = await request.json()
    try:
        workflow = AdaptiveWorkflow(data.get("patient_id"))
        state = await asyncio.to_thread(workflow.tool_event, data.get("operation_id"),
            data.get("action_status"), data.get("session_generation"), data.get("tool_result"))
        if state["session_status"] == "completed":
            await asyncio.to_thread(summarise_if_ready, workflow)
        message = ""
        if state["session_status"] == "active" and data.get("action_status") != "executing":
            message = next((item["content"] for item in state["chat_history"]
                if item["id"] == data.get("operation_id") + ":tool-result"), "")
        return {"status": "ok", "assistant_message": message, "persisted": True, **projection(state)}
    except ValueError as error:
        raise HTTPException(409, str(error))


@router.post("/tool_message")
async def tool_message(request: Request):
    data = await request.json()
    try:
        state = AdaptiveWorkflow(data.get("patient_id")).append_tool_message(
            data.get("operation_id"), data.get("session_generation"), data.get("message"))
        return {"status": "ok", **projection(state)}
    except ValueError as error:
        raise HTTPException(409, str(error))
