from pathlib import Path
import os
import time
import requests, json, threading
from datetime import datetime, timedelta
from fastapi import FastAPI, Request  # type: ignore
from ai_helper import ask_ai

# === Configuration ===
OA_URL = "http://oa:8000/receive_message"
OA_USER_URL = "http://oa:8000/receive_user_message"
SSA_URL = "http://oa:8000/trigger_agent"

MEMORY_FILE = Path("/app/memory/sca_conversations.json")
SCA_AUTO_TRIGGER_SSA_DELAY_SECONDS = int(
    os.getenv("SCA_AUTO_TRIGGER_SSA_DELAY_SECONDS", "45")
)


# === Initialization ===
app = FastAPI()


# === AI Wrapper (支持OpenAI和智谱AI) ===
def ask_gpt(messages):
    """统一的AI调用接口，支持OpenAI GPT和智谱AI"""
    return ask_ai(messages, temperature=0.7)


# === Memory Handlers ===
def load_memory():
    if not MEMORY_FILE.exists():
        return []
    with open(MEMORY_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print("Warning: Memory file is not valid JSON. Starting fresh.", flush=True)
            return []

def save_message(new_record):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
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

    with open(MEMORY_FILE, "w") as f:
        json.dump(records, f, indent=2)


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
    assistant_reply = ask_gpt(initial_prompt)
    #assistant_reply = "Thank you for this session"

    chat_history = [{"role": "assistant", "content": assistant_reply}]

    save_message({
        "patient_id": patient_id,
        "chat_history": chat_history
    })

    def notify_oa():
        try:
            response = requests.post(OA_URL, json={
                "patient_id": patient_id,
                "turn_index": turn_index,
                "message": assistant_reply
            }, timeout=3)
            print(f"Sent HC message to OA for patient {patient_id} (turn {turn_index})", flush=True)
        except Exception as e:
            print(f"Failed to notify OA: {e}", flush=True)

    threading.Thread(target=notify_oa, daemon=True).start()

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

    return {"status": "SCA triggered", "patient_id": patient_id}

@app.post("/receive_message")
async def receive_message(request: Request):
    data = await request.json()
    patient_id = data.get("patient_id")
    user_input = data.get("user_input")
    turn_index = int(data.get("turn_index"))

    if not patient_id:
        return {"status": "error", "reason": "Missing patient_id"}

    print(f"Received '{user_input}' from {patient_id} (turn {turn_index})", flush=True)

    records = load_memory()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    if not patient_entry:
        return {"status": "error", "reason": "Patient session not found"}

    chat_history = patient_entry.get("chat_history")
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

    # Compute review date for next week at 9 AM
    next_review = (datetime.now() + timedelta(weeks=1)).strftime("%A, %B %d at 9:00 AM")

    turn_index += 1

    if(turn_index >= 15):
        # 会话已结束，更新OA中的turn_index并保存
        try:
            oa_response = requests.post(OA_URL, json={
                "patient_id": patient_id,
                "turn_index": 15,  # 设置为15表示会话已结束
                "message": "Session completed."
            })
            if oa_response.status_code == 200:
                print(f"Updated OA with completed session status for patient {patient_id}", flush=True)
        except Exception as e:
            print(f"Error updating OA session status: {e}", flush=True)
        
        # 保存最终状态
        save_message({
            "patient_id": patient_id,
            "chat_history": chat_history,
            "turn_index": 15
        })
        
        return {"status": "done", "reason": "Did all turns", "turn_index": 15}

    assistant_prompt = (
        f"The client said: '{user_input}'. Thank them for their feedback! Tell them that we will take that into account. "
        f"Your next weekly check-in will be on {next_review}. See you then!"
    )

    # GPT generation placeholder
    full_prompt = [
                {"role": "system", "content": "You are a warm, empathetic health coach closing a session."},
                *chat_history,
                {"role": "user", "content": assistant_prompt}
            ]
    assistant_reply = ask_gpt(full_prompt)
    #assistant_reply = assistant_prompt
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

    trigger_ssa(patient_id=patient_id, turn_index=turn_index, source="after_user_reply")

    save_message({
        "patient_id": patient_id,
        "chat_history": chat_history
    })

    return {"status": "message processed", "turn_index": turn_index}
