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

# === Configuration ===
MMA_URL = "http://mma:8000/patient_notes"
OA_URL = "http://oa:8000/receive_message"
OA_USER_URL = "http://oa:8000/receive_user_message"
GRA_URL = "http://oa:8000/trigger_agent"

MEMORY_FILE = Path("/app/memory/soa_conversations.json")
SERVICE_NAME = "soa"


# === Initialization ===
app = FastAPI()


# === AI Wrapper (支持OpenAI和智谱AI) ===
def ask_gpt(messages):
    """统一的AI调用接口，支持OpenAI GPT和智谱AI"""
    return ask_ai(messages, temperature=0.7)


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
        response = requests.get(f"{MMA_URL}/{patient_id}")
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

    system_prompt = "You are a warm, empathetic health coach opening a session."
    initial_prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "assistant", "content": f"Greet '{preferred_name}' and ask about energy level."}
    ]

    # AI调用，添加异常处理
    try:
        assistant_reply = ask_gpt(initial_prompt)
    except Exception as e:
        print(f"Error calling AI service: {e}", flush=True)
        # 使用fallback消息，避免整个流程失败
        if preferred_name and preferred_name != "there":
            assistant_reply = f"Hi {preferred_name}! How are you feeling today? What's your energy level?"
        else:
            assistant_reply = "Hi there! How are you feeling today? What's your energy level?"

    chat_history = [{"role": "assistant", "content": assistant_reply}]

    save_message({
        "patient_id": patient_id,
        "notes": notes,
        "chat_history": chat_history
    })

    try:
        oa_response = requests.post(OA_URL, json={
            "patient_id": patient_id,
            "turn_index": 1,
            "message": assistant_reply
        })
        if oa_response.status_code == 200:
            print(f"Sent HC message to OA for patient {patient_id} (turn 1)", flush=True)
        else:
            print(f"Failed to send message to OA (status {oa_response.status_code})", flush=True)
    except Exception as e:
        print(f"Error sending message to OA: {e}", flush=True)

    return {"status": "SOA triggered", "patient_id": patient_id}

@app.post("/receive_message")
async def receive_message(request: Request):
    data = await request.json()
    patient_id = data.get("patient_id")
    user_input = data.get("user_input")
    turn_index = int(data.get("turn_index"))

    if not patient_id:
        return {"status": "error", "reason": "Missing patient_id"}

    # 检查会话是否已结束
    if turn_index >= 15:
        print(f"Session already completed for {patient_id}, ignoring message", flush=True)
        return {"status": "done", "reason": "Session already completed", "turn_index": 15}

    print(f"Received '{user_input}' from {patient_id} (turn {turn_index})", flush=True)

    records = load_memory()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    if not patient_entry:
        return {"status": "error", "reason": "Patient session not found"}

    chat_history = patient_entry.get("chat_history", [])
    
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
    try:
        oa_user_resp = requests.post(OA_USER_URL, json={
            "patient_id": patient_id,
            "turn_index": turn_index,
            "user_input": user_input
        })
        if oa_user_resp.status_code == 200:
            print(f"Sent user message to OA for patient {patient_id} (turn {turn_index})", flush=True)
        else:
            print(f"Failed to send user message to OA (status {oa_user_resp.status_code})", flush=True)
    except Exception as e:
        print(f"Error sending user message to OA: {e}", flush=True)

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
    if turn_index == 2:
        assistant_prompt = f"The client said: '{user_input}'. If number, ask what it means. If mood, ask why."
    elif turn_index == 3:
        assistant_prompt = f"The client said: '{user_input}'. Reflect empathetically and ask for a positive health moment from last week."
    elif turn_index == 4:
        if user_input.strip():
            assistant_prompt = f"The client said: '{user_input}'. Reflect positively and ask a light follow-up."
        else:
            assistant_prompt = f"The client didn’t share much. Use fallback: '{fallback_text}' to keep the conversation going."
    elif turn_index == 5:
        if user_input.strip():
            assistant_prompt = f"The client said: '{user_input}'. Reflect positively. Do not say goodbye."
        else:
            assistant_prompt = "The client didn’t say much. Share a short encouraging comment without saying goodbye."

    assistant_reply = ""
    if turn_index < 6:
        full_prompt = [
                {"role": "system", "content": "You are a warm, empathetic health coach opening a session."},
                *chat_history,
                {"role": "user", "content": assistant_prompt}
            ]
        try:
            assistant_reply = ask_gpt(full_prompt)
        except Exception as e:
            print(f"Error calling AI service in receive_message: {e}", flush=True)
            # 使用fallback消息
            assistant_reply = assistant_prompt
        chat_history.append({"role": "assistant", "content": assistant_reply})
        try:
            oa_response = requests.post(OA_URL, json={
                "patient_id": patient_id,
                "turn_index": turn_index,
                "message": assistant_reply
            })
            if oa_response.status_code == 200:
                print(f"Sent HC message to OA for patient {patient_id} (turn {turn_index})", flush=True)
            else:
                print(f"Failed to send message to OA (status {oa_response.status_code})", flush=True)
        except Exception as e:
            print(f"Error sending message to OA: {e}", flush=True)
    elif turn_index == 6:
        agent_to_trigger = "GRA"
        try:
            # 触发GRA并等待完成，确保turn_index正确更新
            gra_response = requests.post(GRA_URL, json={
                "patient_id": patient_id,
                "turn_index": turn_index,
                "agent_to_trigger": agent_to_trigger
            }, timeout=10)
            if gra_response.status_code == 200:
                print(f"Triggered {agent_to_trigger} for patient {patient_id}", flush=True)
                # 等待一下，确保GRA的消息已经到达OA并更新turn_index
                import time
                time.sleep(0.5)
            else:
                print(f"Failed to trigger {agent_to_trigger} for patient {patient_id} (status {gra_response.status_code})", flush=True)
        except Exception as e:
            print(f"Error triggering {agent_to_trigger} for patient {patient_id}: {e}", flush=True)

    save_message({
        "patient_id": patient_id,
        "chat_history": chat_history
    })

    return {"status": "message processed", "turn_index": turn_index}
