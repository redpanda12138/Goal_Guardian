from pathlib import Path
import asyncio
import functools
from contextlib import asynccontextmanager
import os
import sys
import time
import requests, json, threading
from datetime import datetime, timedelta
from fastapi import FastAPI, Request  # type: ignore
from ai_helper import ask_ai

for common_dir in (
    Path(__file__).resolve().parent / "common",
    Path(__file__).resolve().parents[1] / "common",
):
    if common_dir.exists() and str(common_dir) not in sys.path:
        sys.path.insert(0, str(common_dir))

from mas_memory_store import load_json, save_json
from prompt_guard import build_coach_prompt, safe_coach_reply

# === Configuration ===
OA_URL = "http://oa:8000/receive_message"
OA_USER_URL = "http://oa:8000/receive_user_message"
SSA_URL = "http://oa:8000/trigger_agent"
REQUEST_TIMEOUT_SECONDS = 15

MEMORY_FILE = Path("/app/memory/sca_conversations.json")
SERVICE_NAME = "sca"
SCA_AUTO_TRIGGER_SSA_DELAY_SECONDS = int(
    os.getenv("SCA_AUTO_TRIGGER_SSA_DELAY_SECONDS", "45")
)


# === Initialization ===
app = FastAPI()
_patient_locks = {}
_patient_locks_guard = asyncio.Lock()


# === AI Wrapper (支持OpenAI和智谱AI) ===
def ask_gpt(messages):
    """统一的AI调用接口，支持OpenAI GPT和智谱AI"""
    return ask_ai(messages, temperature=0.7)


async def run_blocking(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))


@asynccontextmanager
async def patient_session_lock(patient_id):
    async with _patient_locks_guard:
        lock = _patient_locks.setdefault(patient_id, asyncio.Lock())
    async with lock:
        yield


async def post_json(url, payload):
    return await run_blocking(
        requests.post,
        url,
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


async def persist_oa_message(url, payload, label, patient_id, turn_index):
    try:
        response = await post_json(url, payload)
        if response.status_code == 200:
            print(f"Sent {label} to OA for patient {patient_id} (turn {turn_index})", flush=True)
            return True
        print(f"Failed to send {label} to OA (status {response.status_code})", flush=True)
    except Exception as e:
        print(f"Error sending {label} to OA: {e}", flush=True)
    return False


def return_oa_persistence_error(patient_id, turn_index):
    return {
        "status": "error",
        "reason": "OA persistence failed",
        "patient_id": patient_id,
        "turn_index": turn_index,
        "persisted": False,
    }


# === Memory Handlers ===
def load_memory():
    return load_json(SERVICE_NAME, "sca_conversations", [], MEMORY_FILE)

def save_message(new_record):
    records = load_memory()

    updated = False
    for record in records:
        if record.get("patient_id") == new_record.get("patient_id"):
            if "chat_history" in new_record:
                record["chat_history"] = new_record.get("chat_history", [])
            updated = True
            break

    if not updated:
        records.append(new_record)

    save_json(SERVICE_NAME, "sca_conversations", records, MEMORY_FILE)


def has_user_reply(patient_id: str) -> bool:
    records = load_memory()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    if not patient_entry:
        return False
    chat_history = patient_entry.get("chat_history", [])
    return any(
        msg.get("role") == "user" and str(msg.get("content", "")).strip()
        for msg in chat_history
    )


def trigger_ssa(patient_id: str, turn_index: int, source: str) -> None:
    try:
        agent_to_trigger = "SSA"
        oa_response = requests.post(
            SSA_URL,
            json={
                "patient_id": patient_id,
                "turn_index": turn_index,
                "agent_to_trigger": agent_to_trigger
            },
            timeout=5
        )
        if oa_response.status_code == 200:
            print(
                f"Triggered {agent_to_trigger} for patient {patient_id} (source={source})",
                flush=True
            )
        else:
            print(
                f"Failed to trigger {agent_to_trigger} for patient {patient_id} (status {oa_response.status_code}, source={source})",
                flush=True
            )
    except Exception as e:
        print(f"Error triggering SSA for patient {patient_id} (source={source}): {e}", flush=True)


# === API Endpoints ===
@app.post("/trigger")
async def trigger(request: Request):
    data = await request.json()
    patient_id = data.get("patient_id")
    turn_index = data.get("turn_index")

    if not patient_id:
        return {"status": "error", "reason": "Missing patient_id"}

    print(f"SCA was triggered to do weekly SMART goal review for patient {patient_id}", flush=True)

    system_prompt = "You are a warm, empathetic health coach closing a session."
    initial_prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "assistant", "content": (
            f"Thank the client for joining this check-in session. "
            "Ask if they have any feedback or suggestions for how to improve these conversations."
        )}
    ]

    # GPT generation placeholder
    assistant_reply = await run_blocking(ask_gpt, initial_prompt)
    #assistant_reply = "Thank you for this session"

    chat_history = [{"role": "assistant", "content": assistant_reply}]

    persisted = await persist_oa_message(
        OA_URL,
        {
            "patient_id": patient_id,
            "turn_index": turn_index,
            "message": assistant_reply
        },
        "assistant message",
        patient_id,
        turn_index,
    )
    if not persisted:
        return return_oa_persistence_error(patient_id, turn_index)

    save_message({
        "patient_id": patient_id,
        "chat_history": chat_history
    })

    # 兜底逻辑：如果患者在等待窗口内没有回复，则自动触发 SSA，避免流程卡住
    def auto_trigger_ssa_if_no_reply():
        delay_seconds = max(0, SCA_AUTO_TRIGGER_SSA_DELAY_SECONDS)
        if delay_seconds:
            time.sleep(delay_seconds)

        if has_user_reply(patient_id):
            print(
                f"Skip auto-trigger SSA for patient {patient_id}: user reply detected within {delay_seconds}s",
                flush=True
            )
            return

        if turn_index is None:
            print(
                f"Skip auto-trigger SSA for patient {patient_id}: missing turn_index",
                flush=True
            )
            return

        try:
            safe_turn_index = int(turn_index)
        except Exception:
            print(
                f"Skip auto-trigger SSA for patient {patient_id}: invalid turn_index={turn_index}",
                flush=True
            )
            return

        trigger_ssa(
            patient_id=patient_id,
            turn_index=safe_turn_index,
            source=f"auto_no_user_reply_{delay_seconds}s"
        )

    threading.Thread(target=auto_trigger_ssa_if_no_reply, daemon=True).start()

    return {
        "status": "SCA triggered",
        "patient_id": patient_id,
        "assistant_message": assistant_reply,
        "persisted": True,
    }

@app.post("/receive_message")
async def receive_message(request: Request):
    data = await request.json()
    patient_id = data.get("patient_id")
    if not patient_id:
        return {"status": "error", "reason": "Missing patient_id"}
    async with patient_session_lock(patient_id):
        return await _receive_message_locked(data)


async def _receive_message_locked(data):
    patient_id = data.get("patient_id")
    user_input = data.get("user_input")
    turn_index = int(data.get("turn_index"))

    print(f"Received '{user_input}' from {patient_id} (turn {turn_index})", flush=True)

    records = load_memory()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    if not patient_entry:
        return {"status": "error", "reason": "Patient session not found"}

    chat_history = list(patient_entry.get("chat_history", []))
    chat_history.append({"role": "user", "content": user_input})

    # 将用户消息同步到 OA 的 goal_reviews.json（role: user）
    user_persisted = await persist_oa_message(
        OA_USER_URL,
        {
            "patient_id": patient_id,
            "turn_index": turn_index,
            "user_input": user_input
        },
        "user message",
        patient_id,
        turn_index,
    )
    if not user_persisted:
        return return_oa_persistence_error(patient_id, turn_index)

    # Compute review date for next week at 9 AM
    next_review = (datetime.now() + timedelta(weeks=1)).strftime("%A, %B %d at 9:00 AM")

    turn_index += 1

    if(turn_index >= 15):
        completed_persisted = await persist_oa_message(
            OA_URL,
            {
                "patient_id": patient_id,
                "turn_index": 15,
                "message": "Session completed."
            },
            "completion message",
            patient_id,
            15,
        )
        if not completed_persisted:
            return return_oa_persistence_error(patient_id, 15)
        
        save_message({
            "patient_id": patient_id,
            "chat_history": chat_history,
            "turn_index": 15
        })
        
        return {"status": "done", "reason": "Did all turns", "turn_index": 15}

    assistant_fallback = (
        "Thank you for sharing that feedback. We will take it into account. "
        f"Your next weekly check-in will be on {next_review}. See you then!"
    )
    assistant_prompt = build_coach_prompt(
        user_input,
        (
            "Thank the client for their feedback, say it will be taken into account, "
            f"and tell them their next weekly check-in will be on {next_review}. Close warmly."
        ),
    )

    # GPT generation placeholder
    full_prompt = [
                {"role": "system", "content": "You are a warm, empathetic health coach closing a session."},
                *chat_history,
                {"role": "user", "content": assistant_prompt}
            ]
    try:
        assistant_reply = safe_coach_reply(await run_blocking(ask_gpt, full_prompt), assistant_fallback)
    except Exception as e:
        print(f"Error calling AI service in SCA receive_message: {e}", flush=True)
        assistant_reply = assistant_fallback
    chat_history.append({"role": "assistant", "content": assistant_reply})
    assistant_persisted = await persist_oa_message(
        OA_URL,
        {
            "patient_id": patient_id,
            "turn_index": turn_index,
            "message": assistant_reply
        },
        "assistant message",
        patient_id,
        turn_index,
    )
    if not assistant_persisted:
        return return_oa_persistence_error(patient_id, turn_index)

    trigger_ssa(patient_id=patient_id, turn_index=turn_index, source="after_user_reply")

    save_message({
        "patient_id": patient_id,
        "chat_history": chat_history
    })

    return {
        "status": "message processed",
        "turn_index": turn_index,
        "assistant_message": assistant_reply,
        "persisted": True,
    }
