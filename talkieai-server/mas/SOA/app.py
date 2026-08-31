import asyncio
import functools
from contextlib import asynccontextmanager
import requests, json
from pathlib import Path
import sys
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
from adaptive_agent import generate_stage_reply

# === Configuration ===
MMA_URL = "http://mma:8000/patient_notes"
OA_URL = "http://oa:8000/receive_message"
OA_USER_URL = "http://oa:8000/receive_user_message"
GRA_URL = "http://oa:8000/trigger_agent"
REQUEST_TIMEOUT_SECONDS = 15
AGENT_TRANSITION_TIMEOUT_SECONDS = 90

MEMORY_FILE = Path("/app/memory/soa_conversations.json")
SERVICE_NAME = "soa"


# === Initialization ===
app = FastAPI()


@app.post("/adaptive_reply")
async def adaptive_reply(request: Request):
    data = await request.json()
    def model(messages, temperature, tools):
        return {"content": ask_ai(messages, temperature=temperature)}
    return await run_blocking(generate_stage_reply, "SOA", data, model)


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
    return load_json(SERVICE_NAME, "soa_conversations", [], MEMORY_FILE)

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

    save_json(SERVICE_NAME, "soa_conversations", records, MEMORY_FILE)


# === API Endpoints ===
@app.post("/trigger")
async def trigger(request: Request):
    data = await request.json()
    patient_id = data.get("patient_id")
    if not patient_id:
        return {"status": "error", "reason": "Missing patient_id"}

    print(f"SOA was triggered to do weekly SMART goal review for patient {patient_id}", flush=True)

    try:
        response = await run_blocking(requests.get, f"{MMA_URL}/{patient_id}")
        if response.status_code == 200:
            notes = response.json()
            print(f"Retrieved {notes} from MMA for patient {patient_id}", flush=True)
        else:
            print(f"Failed to fetch notes from MMA (status {response.status_code})", flush=True)
            return {"status": "failed", "reason": "MMA fetch error"}
    except Exception as e:
        print(f"Error contacting MMA: {e}", flush=True)
        return {"status": "failed", "reason": str(e)}

    preferred_name = notes.get("preferred_name") or "there"

    system_prompt = (
        "You are a warm, empathetic health coach opening a session. "
        "Return only the message that should be shown to the client."
    )
    initial_fallback = (
        f"Hi {preferred_name}! How are you feeling today? What's your energy level?"
        if preferred_name and preferred_name != "there"
        else "Hi there! How are you feeling today? What's your energy level?"
    )
    initial_prompt = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": build_coach_prompt(
                f"Preferred name: {preferred_name}",
                "Greet the client warmly and ask about their energy level.",
            ),
        },
    ]

    # AI调用，添加异常处理
    try:
        assistant_reply = safe_coach_reply(await run_blocking(ask_gpt, initial_prompt), initial_fallback)
    except Exception as e:
        print(f"Error calling AI service: {e}", flush=True)
        assistant_reply = initial_fallback

    chat_history = [{"role": "assistant", "content": assistant_reply}]

    persisted = await persist_oa_message(
        OA_URL,
        {
            "patient_id": patient_id,
            "turn_index": 1,
            "message": assistant_reply
        },
        "assistant message",
        patient_id,
        1,
    )
    if not persisted:
        return return_oa_persistence_error(patient_id, 1)

    save_message({
        "patient_id": patient_id,
        "notes": notes,
        "chat_history": chat_history
    })

    return {
        "status": "SOA triggered",
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

    # 检查会话是否已结束
    if turn_index >= 15:
        print(f"Session already completed for {patient_id}, ignoring message", flush=True)
        return {"status": "done", "reason": "Session already completed", "turn_index": 15}

    print(f"Received '{user_input}' from {patient_id} (turn {turn_index})", flush=True)

    records = load_memory()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    if not patient_entry:
        return {"status": "error", "reason": "Patient session not found"}

    chat_history = list(patient_entry.get("chat_history", []))
    
    # 如果turn_index >= 6，SOA不应该再处理，应该由GRA处理
    if turn_index >= 6:
        print(f"SOA received turn_index {turn_index} message, but SOA only handles turns 1-5. This should be handled by GRA.", flush=True)
        return {"status": "error", "reason": f"SOA only handles turns 1-5, but received turn {turn_index}. This message should be sent to GRA."}
    
    # 检查是否已经处理过这个turn_index的用户消息，避免重复处理
    user_messages = [msg for msg in chat_history if msg.get("role") == "user"]
    expected_user_count = turn_index  # turn_index=5意味着应该有5条user消息
    
    if len(user_messages) >= expected_user_count:
        # 检查最后一条user消息是否与当前输入相同
        if user_messages and user_messages[-1].get("content") == user_input:
            print(f"Message already processed for {patient_id} at turn {turn_index}, skipping duplicate", flush=True)
            # 返回当前状态，不重复处理
            current_turn = turn_index + 1
            return {"status": "already_processed", "turn_index": current_turn}
    
    # 添加用户消息
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

    notes = patient_entry.get("notes", {})

    fallback_sources = ["family", "friends", "travel", "hobbies"]
    fallback_text = ""
    for source in fallback_sources:
        values = notes.get(source, [])
        if values:
            fallback_text = values[0]
            break

    turn_index += 1

    assistant_prompt = ""
    assistant_fallback = "Thanks for sharing. Could you tell me a little more about that?"
    if turn_index == 2:
        assistant_prompt = build_coach_prompt(
            user_input,
            "If the client gave a number, ask what it means. If they described a mood, ask why. Keep it brief.",
        )
        assistant_fallback = "Thanks for sharing. Could you tell me a little more about what that means for you?"
    elif turn_index == 3:
        assistant_prompt = build_coach_prompt(
            user_input,
            "Reflect empathetically and ask for one positive health moment from last week.",
        )
        assistant_fallback = "I'm glad you shared that. What was one positive health moment from last week?"
    elif turn_index == 4:
        if user_input.strip():
            assistant_prompt = build_coach_prompt(
                user_input,
                "Reflect positively and ask one light follow-up question.",
            )
            assistant_fallback = "That sounds like a positive moment. What helped make that happen?"
        else:
            assistant_prompt = build_coach_prompt(
                user_input,
                f"The client did not share much. Use this topic if useful: {fallback_text}. Ask a gentle follow-up.",
            )
            assistant_fallback = (
                f"No worries. Could you tell me about something connected to {fallback_text} that felt positive recently?"
                if fallback_text
                else "No worries. Could you share one small thing that felt positive recently?"
            )
    elif turn_index == 5:
        if user_input.strip():
            assistant_prompt = build_coach_prompt(
                user_input,
                "Reflect positively. Do not say goodbye and do not ask another question.",
            )
            assistant_fallback = "Thank you for reflecting on that. It is encouraging to notice these moments and what supports them."
        else:
            assistant_prompt = build_coach_prompt(
                user_input,
                "Share a short encouraging comment without saying goodbye.",
            )
            assistant_fallback = "Thank you for staying with the reflection. Even small observations can be useful."

    assistant_reply = ""
    if turn_index < 6:
        full_prompt = [
                {"role": "system", "content": "You are a warm, empathetic health coach opening a session."},
                *chat_history,
                {"role": "user", "content": assistant_prompt}
            ]
        try:
            assistant_reply = safe_coach_reply(await run_blocking(ask_gpt, full_prompt), assistant_fallback)
        except Exception as e:
            print(f"Error calling AI service in receive_message: {e}", flush=True)
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
    elif turn_index == 6:
        agent_to_trigger = "GRA"
        try:
            # 触发GRA并等待完成，确保turn_index正确更新
            gra_response = await run_blocking(requests.post, GRA_URL, json={
                "patient_id": patient_id,
                "turn_index": turn_index,
                "agent_to_trigger": agent_to_trigger
            }, timeout=AGENT_TRANSITION_TIMEOUT_SECONDS)
            if gra_response.status_code == 200:
                print(f"Triggered {agent_to_trigger} for patient {patient_id}", flush=True)
                # 等待一下，确保GRA的消息已经到达OA并更新turn_index
                await asyncio.sleep(0.5)
            else:
                print(f"Failed to trigger {agent_to_trigger} for patient {patient_id} (status {gra_response.status_code})", flush=True)
        except Exception as e:
            print(f"Error triggering {agent_to_trigger} for patient {patient_id}: {e}", flush=True)

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
