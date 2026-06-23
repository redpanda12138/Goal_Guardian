from pathlib import Path
import os
import sys
import time, threading, json, requests, asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Request, HTTPException

for common_dir in (
    Path(__file__).resolve().parent / "common",
    Path(__file__).resolve().parents[1] / "common",
):
    if common_dir.exists() and str(common_dir) not in sys.path:
        sys.path.insert(0, str(common_dir))

from mas_memory_store import load_json, save_json, memory_exists

# === Configuration ===
MMA_URL = "http://mma:8000/extract"
AGENT_URL = "http://{agent}:8000/trigger"
SERVICE_NAME = "oa"

SESSION_NOTES_FILE = Path("memory/session_notes_mock.json")
REVIEW_SCHEDULE_FILE = Path("memory/review_schedule.json")
GOAL_REVIEW_FILE = Path("memory/goal_reviews.json")

# 预约时间：前端宜传 ISO8601 UTC（…Z）；无时区字符串按此墙钟时区解释（兼容旧数据）
try:
    OA_SCHEDULE_TZ = ZoneInfo(os.getenv("OA_SCHEDULE_TZ", "Asia/Shanghai"))
except Exception:
    OA_SCHEDULE_TZ = timezone(timedelta(hours=8))


def _parse_to_utc(dt_str: str) -> datetime | None:
    """将预约时间解析为 UTC（aware）。无时区则视为 OA_SCHEDULE_TZ 墙钟时间。"""
    if not dt_str or not str(dt_str).strip():
        return None
    try:
        s = str(dt_str).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=OA_SCHEDULE_TZ)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def utc_now_truncate_minute() -> datetime:
    return datetime.now(timezone.utc).replace(second=0, microsecond=0)


def format_utc_iso_z(dt_utc: datetime) -> str:
    return dt_utc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# === Initialization ===
app = FastAPI()


# === Memory Handlers ===
def load_review_schedule():
    return load_json(SERVICE_NAME, "review_schedule", {}, REVIEW_SCHEDULE_FILE)

def load_goal_reviews():
    raw = load_json(SERVICE_NAME, "goal_reviews", [], GOAL_REVIEW_FILE)
    return [json.loads(e) if isinstance(e, str) else e for e in raw]


def save_goal_reviews(records):
    save_json(SERVICE_NAME, "goal_reviews", records, GOAL_REVIEW_FILE)


def save_review_schedule(schedule):
    save_json(SERVICE_NAME, "review_schedule", schedule, REVIEW_SCHEDULE_FILE)

def save_message(new_record):
    records = load_goal_reviews()

    updated = False
    for record in records:
        if record.get("patient_id") == new_record.get("patient_id"):
            if "chat_history" in new_record:
                existing_history = record.get("chat_history", [])
                new_history = new_record.get("chat_history", [])
                
                # 避免重复添加相同的消息
                for new_msg in new_history:
                    # 检查是否已经存在相同的消息（基于内容和角色）
                    is_duplicate = False
                    for existing_msg in existing_history:
                        if (existing_msg.get("role") == new_msg.get("role") and 
                            existing_msg.get("content") == new_msg.get("content")):
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        existing_history.append(new_msg)
                
                record["chat_history"] = existing_history
                
                # 基于chat_history的实际长度计算turn_index
                # turn_index = assistant消息的数量（因为每个turn包含一个assistant消息）
                # 注意：turn_index应该表示当前会话的轮次（1-15），不应该无限累加
                assistant_count = sum(1 for msg in existing_history if msg.get("role") == "assistant")
                
                # 如果turn_index已经>=15，说明会话已完成，不应该继续累加
                # 如果超过15，自动重置（防止历史累积）
                if assistant_count > 15:
                    print(f"⚠️ Warning: turn_index ({assistant_count}) exceeds 15 for patient {record.get('patient_id')}. Auto-resetting in save_message.", flush=True)
                    record["turn_index"] = 0
                    record["chat_history"] = []
                else:
                    record["turn_index"] = assistant_count
            
            # 如果明确提供了turn_index，使用它（但优先使用计算值）
            # 注意：不接受超过15的turn_index，防止历史累积
            if "turn_index" in new_record and new_record.get("turn_index") is not None:
                provided_turn = new_record.get("turn_index")
                current_turn = record.get("turn_index", 0)
                # 只有当提供的turn_index大于当前计算的turn_index且不超过15时才更新
                if provided_turn > current_turn and provided_turn <= 15:
                    record["turn_index"] = provided_turn
                elif provided_turn > 15:
                    print(f"⚠️ Warning: Provided turn_index ({provided_turn}) exceeds 15 for patient {record.get('patient_id')}. Ignoring and using calculated value.", flush=True)
            
            updated = True
            break

    if not updated:
        # 对于新记录，也计算turn_index
        if "chat_history" in new_record:
            assistant_count = sum(1 for msg in new_record.get("chat_history", []) if msg.get("role") == "assistant")
            new_record["turn_index"] = new_record.get("turn_index", assistant_count)
        records.append(new_record)

    save_goal_reviews(records)


# === Trigger Helper (used by both loop and endpoint) ===
def trigger_agent_sync(patient_id: str, turn_index: int, agent_to_trigger: str) -> dict:
    agent = agent_to_trigger.lower()
    url = AGENT_URL.format(agent=agent)

    print(f"OA received {agent_to_trigger} trigger request for {patient_id}", flush=True)

    payload = {
        "patient_id": patient_id,
        "turn_index": turn_index  # default for most agents
    }

    # Special logic for SSA
    if agent == "ssa":
        if not memory_exists(SERVICE_NAME, "goal_reviews", GOAL_REVIEW_FILE):
            return {"status": "error", "reason": "Goal review file not found."}

        try:
            entries = load_goal_reviews()
            patient_entry = next((e for e in entries if e.get("patient_id") == patient_id), None)

            if not patient_entry:
                return {"status": "error", "reason": f"No entry found in goal_reviews.json for patient {patient_id}"}

            payload = {
                "patient_id": patient_id,
                "chat_history": patient_entry.get("chat_history")
            }

        except Exception as e:
            return {"status": "error", "reason": f"Failed to load SCA payload: {e}"}

    try:
        # 关键：给外部服务调用加 timeout，避免 OA 在某次触发中卡死
        response = requests.post(url, json=payload, timeout=(3, 25))
        response.raise_for_status()
        try:
            body = response.json()
        except Exception:
            body = {}
        # SOA 等在业务失败时仍可能返回 HTTP 200 + status: failed
        sub = (body.get("status") or "").lower()
        if sub in ("failed", "error"):
            reason = body.get("reason") or body.get("message") or str(body)
            print(
                f"Agent {agent_to_trigger} returned failure for {patient_id}: {reason}",
                flush=True,
            )
            return {"status": "error", "reason": reason}
        print(f"Triggered {agent_to_trigger} for patient {patient_id}", flush=True)
        return {"status": "ok"}
    except Exception as e:
        print(f"Failed to trigger {agent_to_trigger}: {e}", flush=True)
        return {"status": "error", "reason": str(e)}

def reset_patient_session_state(patient_id: str) -> None:
    """
    清空 OA 中该患者在 goal_reviews 里的会话状态。
    定时预约再次触发 SOA 时，若开场白与上一轮最后一条 assistant 相同，
    receive_message 会去重跳过，导致用户看不到“新回合”——故调度触发前必须先重置。
    """
    records = load_goal_reviews()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    if not patient_entry:
        records.append(
            {"patient_id": patient_id, "turn_index": 0, "chat_history": []}
        )
    else:
        patient_entry["turn_index"] = 0
        patient_entry["chat_history"] = []
    save_goal_reviews(records)
    print(
        f"🗓️ Reset OA session state for {patient_id} before scheduled SOA trigger",
        flush=True,
    )


def trigger_mma():

    if not memory_exists(SERVICE_NAME, "session_notes_mock", SESSION_NOTES_FILE):
        return {"status": "error", "reason": "session_notes_mock.json not found"}

    try:
        payload = load_json(SERVICE_NAME, "session_notes_mock", [], SESSION_NOTES_FILE)

        if not isinstance(payload, list) or not all(isinstance(p, dict) for p in payload):
            return {"status": "error", "reason": "Invalid JSON structure. Expected a list of dicts."}

        # MMA 提取可能稍慢，但也必须加 timeout，避免阻塞 OA
        mma_response = requests.post(MMA_URL, json=payload, timeout=(3, 120))
        mma_response.raise_for_status()

        return {
            "status": "ok",
            "sent": len(payload),
            "mma_status": mma_response.status_code,
            "mma_response": mma_response.json()
        }

    except Exception as e:
        return {"status": "error", "reason": str(e)}


def apply_hourly_review_triggers(schedule: dict, now_utc: datetime) -> list[str]:
    """
    按预约时间触发 SOA：
    - 触发条件：now_utc >= next_review_time（均为 UTC，按分钟截断比较）
    - 仅触发一次：triggered=False 才会触发，触发后置为 True
    """
    triggered_ids: list[str] = []
    changed = False

    now_utc = now_utc.astimezone(timezone.utc).replace(second=0, microsecond=0)

    for patient_id, info in schedule.get("patients", {}).items():
        next_review_utc = _parse_to_utc(info.get("next_review_time") or "")
        if next_review_utc is None:
            continue
        next_review_utc = next_review_utc.replace(second=0, microsecond=0)

        already_triggered = bool(info.get("triggered", False))
        if (not already_triggered) and now_utc >= next_review_utc:
            # 避免与上一轮相同的 SOA 开场白被 receive_message 去重丢弃
            reset_patient_session_state(patient_id)
            result = trigger_agent_sync(patient_id, turn_index=1, agent_to_trigger="SOA")
            # 仅 SOA 真正触发成功才标记已触发，否则下次半点仍会重试
            if result.get("status") == "ok":
                info["triggered"] = True
                info["triggered_at"] = format_utc_iso_z(now_utc)
                # 规范化存储，避免下次再按错误时区解析
                info["next_review_time"] = format_utc_iso_z(next_review_utc)
                triggered_ids.append(patient_id)
                changed = True
            else:
                print(
                    f"⚠️ Scheduled SOA failed for {patient_id}, not marking triggered: {result}",
                    flush=True,
                )

    if changed:
        save_review_schedule(schedule)

    return triggered_ids


# === Orchestration Loop ===
def orchestration_loop():
    time.sleep(1)
    print("OA started", flush=True)
    
    # 记录上次重置的日期，避免同一天重复重置
    last_reset_date = None
    # 避免在同一个半小时窗口内重复触发
    last_check_slot: str | None = None

    while True:
        now_utc = datetime.now(timezone.utc)
        now_slot = now_utc.replace(second=0, microsecond=0)

        # 每半小时检查一次：minute 为 0 或 30
        # 使用 last_check_slot 防止在同一分钟内被重复调用
        if (now_slot.minute % 30 == 0) and (now_slot.second == 0):
            slot_key = now_slot.isoformat()
            if slot_key != last_check_slot:
                last_check_slot = slot_key
                print(f"[{now_slot}] Half-hour check-in running...", flush=True)

                schedule = load_review_schedule()
                apply_hourly_review_triggers(schedule, now_slot)

                # Triggering MMA to extract new session notes once a day (at midnight 00:00)
                if now_slot.hour == 0 and now_slot.minute == 0:
                    print(f"[{now_slot}] Extracting infos from new health coaching notes...", flush=True)
                    trigger_mma()

                # 每天凌晨2点自动重置所有会话计数（避免与MMA任务冲突）
                if now_slot.hour == 2 and now_slot.minute == 0 and last_reset_date != now_slot.date():
                    print(f"[{now_slot}] Auto-resetting all session counts...", flush=True)
                    try:
                        records = load_goal_reviews()
                        reset_count = 0
                        
                        for patient_entry in records:
                            if patient_entry.get("turn_index", 0) > 0 or len(patient_entry.get("chat_history", [])) > 0:
                                patient_entry["turn_index"] = 0
                                patient_entry["chat_history"] = []
                                reset_count += 1
                        
                        if reset_count > 0:
                            save_goal_reviews(records)
                            
                            print(f"[{now_slot}] Auto-reset completed: {reset_count} sessions reset", flush=True)
                        else:
                            print(f"[{now_slot}] No sessions to reset", flush=True)
                        
                        last_reset_date = now_slot.date()
                    except Exception as e:
                        print(f"[{now_slot}] Failed to auto-reset sessions: {e}", flush=True)

                # 当前窗口已处理完，等待 1 分钟避免重复触发
                time.sleep(60)
                continue

        # 非窗口时段每 10 秒检查一次
        time.sleep(10)


# === API Endpoints ===
@app.post("/new_sessions")
async def receive_new_sessions(request: Request):
    payload = await request.json()
    print(f"OA received new sessions for {len(payload)} patients.", flush=True)

    schedule = load_review_schedule()
    schedule.setdefault("patients", {})

    now_utc = datetime.now(timezone.utc)
    invalid_entries = []
    for entry in payload:
        patient_id = entry.get("study_id")
        if not patient_id:
            continue

        date_str = entry.get("date")
        if date_str:
            # 设定了预约时间：按预约时间触发，且必须 >= 当前时间（UTC）
            next_review_utc = _parse_to_utc(date_str)
            if next_review_utc is None:
                invalid_entries.append({
                    "study_id": patient_id,
                    "reason": f"Invalid datetime format: {date_str}"
                })
                continue

            if next_review_utc < now_utc:
                invalid_entries.append({
                    "study_id": patient_id,
                    "reason": f"date earlier than current time: {date_str}"
                })
                continue
        else:
            # 未设定时间：默认 7 天后 09:00（OA_SCHEDULE_TZ 墙钟）触发
            ref_local = datetime.now(OA_SCHEDULE_TZ) + timedelta(days=7)
            next_local = ref_local.replace(hour=9, minute=0, second=0, microsecond=0)
            next_review_utc = next_local.astimezone(timezone.utc)

        schedule["patients"][patient_id] = {
            "next_review_time": format_utc_iso_z(next_review_utc),
            "triggered": False,
            "triggered_at": None
        }

    if invalid_entries:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "invalid_entries": invalid_entries}
        )

    save_review_schedule(schedule)

    print(f"OA memory updated for {len(payload)} patients.", flush=True)
    return {"status": "received", "patients": len(payload)}

@app.post("/receive_message")
async def receive_message(request: Request):
    data = await request.json()
    patient_id = data.get("patient_id")
    turn_index = data.get("turn_index")
    assistant_message = data.get("message")

    if not patient_id or assistant_message is None:
        return {"status": "error", "reason": "Missing data"}

    # 检查是否已经存在相同的消息，避免重复处理
    records = load_goal_reviews()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    
    if patient_entry:
        existing_history = patient_entry.get("chat_history", [])
        # 检查最后一条assistant消息是否与当前消息相同
        if existing_history:
            last_msg = existing_history[-1]
            if (last_msg.get("role") == "assistant" and 
                last_msg.get("content") == assistant_message):
                # 消息已存在，跳过
                current_turn = patient_entry.get("turn_index", 0)
                print(f"Message already exists for {patient_id} at turn {current_turn}, skipping duplicate", flush=True)
                return {"status": "ok", "message": "duplicate_ignored", "turn_index": current_turn}

    message = {
        "patient_id": patient_id,
        "turn_index": turn_index,  # 可选，save_message会基于chat_history重新计算
        "chat_history": [
            {"role": "assistant", "content": assistant_message}
        ]
    }

    save_message(message)
    
    # 获取更新后的turn_index
    records = load_goal_reviews()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    actual_turn_index = patient_entry.get("turn_index", turn_index) if patient_entry else turn_index
    
    print(f"Received message '{assistant_message[:50]}...' from a HC for patient {patient_id} (turn {actual_turn_index})", flush=True)
    return {"status": "ok", "turn_index": actual_turn_index}

@app.post("/receive_user_message")
async def receive_user_message(request: Request):
    """
    接收并保存用户消息到goal_reviews.json
    这样MMA可以从完整的对话历史中提取patient info和goals
    """
    data = await request.json()
    patient_id = data.get("patient_id")
    turn_index = data.get("turn_index")
    user_message = data.get("user_input") or data.get("message")

    print(f"🔵 OA received user message request: patient_id={patient_id}, turn_index={turn_index}, message_length={len(user_message) if user_message else 0}", flush=True)

    if not patient_id or user_message is None:
        print(f"❌ OA receive_user_message error: Missing patient_id or user_input", flush=True)
        return {"status": "error", "reason": "Missing patient_id or user_input"}

    # 检查是否已经存在相同的消息，避免重复处理
    records = load_goal_reviews()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    
    if patient_entry:
        existing_history = patient_entry.get("chat_history", [])
        # 检查最后一条user消息是否与当前消息相同
        if existing_history:
            last_msg = existing_history[-1]
            if (last_msg.get("role") == "user" and 
                last_msg.get("content") == user_message):
                # 消息已存在，跳过
                current_turn = patient_entry.get("turn_index", 0)
                print(f"⚠️ User message already exists for {patient_id} at turn {current_turn}, skipping duplicate", flush=True)
                return {"status": "ok", "message": "duplicate_ignored", "turn_index": current_turn}

    message = {
        "patient_id": patient_id,
        "turn_index": turn_index,  # 可选，save_message会基于chat_history重新计算
        "chat_history": [
            {"role": "user", "content": user_message}
        ]
    }

    save_message(message)
    
    # 获取更新后的turn_index
    records = load_goal_reviews()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    actual_turn_index = patient_entry.get("turn_index", turn_index) if patient_entry else turn_index
    
    # 验证消息是否被保存
    verify_records = load_goal_reviews()
    verify_entry = next((r for r in verify_records if r.get("patient_id") == patient_id), None)
    if verify_entry:
        user_count = sum(1 for msg in verify_entry.get("chat_history", []) if msg.get("role") == "user")
        assistant_count = sum(1 for msg in verify_entry.get("chat_history", []) if msg.get("role") == "assistant")
        print(f"✅ Saved user message for patient {patient_id} (turn {actual_turn_index}): user_msgs={user_count}, assistant_msgs={assistant_count}", flush=True)
    else:
        print(f"⚠️ Warning: User message saved but patient entry not found in verification", flush=True)
    
    return {"status": "ok", "turn_index": actual_turn_index}

@app.post("/trigger_agent")
async def trigger_agent(request: Request):
    data = await request.json()
    patient_id = data.get("patient_id")
    turn_index = data.get("turn_index")
    agent_to_trigger = data.get("agent_to_trigger")

    if not patient_id:
        return {"status": "error", "reason": "Missing patient_id"}
    if not turn_index:
        return {"status": "error", "reason": "Missing turn_index"}
    if not agent_to_trigger:
        return {"status": "error", "reason": "Missing agent_to_trigger"}

    return trigger_agent_sync(patient_id, turn_index, agent_to_trigger)

@app.get("/next_review_time/{patient_id}")
async def next_review_time(patient_id: str):
    """
    获取指定患者的预约时间（用于前端展示）。
    - 始终返回文件中保存的 next_review_time，便于主页显示用户已预约的时点。
    - triggered / triggered_at 表示该时点是否已触发过 SOA（到点后由定时任务置位）。
    """
    schedule = load_review_schedule()
    info = schedule.get("patients", {}).get(patient_id)
    if not info:
        return {
            "status": "ok",
            "patient_id": patient_id,
            "next_review_time": None,
            "triggered": False,
            "triggered_at": None,
        }

    next_time = info.get("next_review_time")
    triggered = bool(info.get("triggered", False))

    return {
        "status": "ok",
        "patient_id": patient_id,
        "next_review_time": next_time,
        "triggered": triggered,
        "triggered_at": info.get("triggered_at"),
    }

@app.get("/conversation_history/{patient_id}")
async def get_conversation_history(patient_id: str):
    """
    获取指定患者的完整对话历史
    """
    records = load_goal_reviews()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    
    if not patient_entry:
        return {
            "status": "not_found",
            "patient_id": patient_id,
            "message": "No conversation history found for this patient"
        }
    
    return {
        "status": "ok",
        "patient_id": patient_id,
        "turn_index": patient_entry.get("turn_index", 0),
        "chat_history": patient_entry.get("chat_history", []),
        "session_status": "active" if patient_entry.get("turn_index", 0) < 15 else "completed"
    }

@app.get("/session_status/{patient_id}")
async def get_session_status(patient_id: str):
    """
    获取指定患者的当前会话状态
    """
    records = load_goal_reviews()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    
    if not patient_entry:
        print(f"📋 Session status check: patient {patient_id} - no entry found", flush=True)
        return {
            "status": "no_session",
            "patient_id": patient_id,
            "message": "No active session found"
        }
    
    turn_index = patient_entry.get("turn_index", 0)
    chat_history_len = len(patient_entry.get("chat_history", []))
    
    # 如果turn_index异常大（>15），说明可能是历史累积，自动重置
    if turn_index > 15:
        print(f"⚠️ Warning: turn_index ({turn_index}) exceeds 15 for patient {patient_id}. Auto-resetting session.", flush=True)
        old_turn_index = turn_index
        old_history_len = chat_history_len
        patient_entry["turn_index"] = 0
        patient_entry["chat_history"] = []
        try:
            save_goal_reviews(records)
            print(f"✅ Auto-reset completed: patient {patient_id} turn_index {old_turn_index} -> 0, chat_history {old_history_len} -> 0", flush=True)
            turn_index = 0
            chat_history_len = 0
        except Exception as e:
            print(f"❌ Failed to auto-reset: {e}", flush=True)
    
    session_status = "active" if turn_index < 15 else "completed"
    
    # 根据turn_index判断当前代理
    if turn_index <= 6:
        current_agent = "SOA"
    elif turn_index <= 13:
        current_agent = "GRA"
    elif turn_index <= 15:
        current_agent = "SCA"
    else:
        current_agent = "COMPLETED"
    
    # 计算user和assistant消息的数量，用于调试
    user_count = sum(1 for msg in patient_entry.get("chat_history", []) if msg.get("role") == "user")
    assistant_count = sum(1 for msg in patient_entry.get("chat_history", []) if msg.get("role") == "assistant")
    print(f"📋 Session status for patient {patient_id}: turn_index={turn_index} (assistant_msgs={assistant_count}, user_msgs={user_count}, total_msgs={chat_history_len}), session_status={session_status}, current_agent={current_agent}", flush=True)
    
    return {
        "status": "ok",
        "patient_id": patient_id,
        "turn_index": turn_index,
        "current_agent": current_agent,
        "session_status": session_status,
        "total_turns": chat_history_len
    }

@app.post("/reset_session/{patient_id}")
async def reset_session(patient_id: str):
    """
    重置指定患者的会话状态（清空chat_history和重置turn_index）
    """
    print(f"🔄 Received reset request for patient {patient_id}", flush=True)

    records = load_goal_reviews()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    old_turn_index = patient_entry.get("turn_index", 0) if patient_entry else None
    old_history_len = len(patient_entry.get("chat_history", [])) if patient_entry else 0

    try:
        reset_patient_session_state(patient_id)
        print(f"✅ Saved goal_reviews.json successfully", flush=True)
    except Exception as e:
        print(f"❌ Failed to save goal_reviews.json: {e}", flush=True)
        return {
            "status": "error",
            "patient_id": patient_id,
            "message": f"Failed to save reset: {e}",
            "turn_index": old_turn_index,
        }
    
    # 验证重置结果
    verify_records = load_goal_reviews()
    verify_entry = next((r for r in verify_records if r.get("patient_id") == patient_id), None)
    if verify_entry:
        verify_turn = verify_entry.get("turn_index", -1)
        verify_history_len = len(verify_entry.get("chat_history", []))
        print(f"✅ Verified reset: patient {patient_id} now has turn_index={verify_turn}, chat_history length={verify_history_len}", flush=True)
    
    return {
        "status": "ok",
        "patient_id": patient_id,
        "message": "Session reset successfully",
        "turn_index": 0,
        "old_turn_index": old_turn_index,
        "old_history_length": old_history_len
    }

# === 定时调度 HTTP 端点（供 talkieai-server 或外部 cron 调用）===
@app.post("/trigger_mma")
async def api_trigger_mma():
    """
    手动触发 MMA 提取会话笔记（对应每天 00:00 的定时任务）
    """
    # 把阻塞任务放到线程里，避免阻塞 FastAPI 事件循环
    result = await asyncio.to_thread(trigger_mma)
    return result

@app.post("/trigger_hourly_check")
async def api_trigger_hourly_check():
    """
    手动触发整点检查（检查 review_schedule，到达预约时间则触发 SOA）
    """
    now_utc = utc_now_truncate_minute()
    schedule = load_review_schedule()
    triggered = await asyncio.to_thread(apply_hourly_review_triggers, schedule, now_utc)
    return {
        "status": "ok",
        "triggered": triggered,
        "checked_at": format_utc_iso_z(now_utc),
    }

@app.post("/trigger_daily_reset")
async def api_trigger_daily_reset():
    """
    手动触发每日重置（对应每天 02:00 的定时任务，重置所有患者 turn_index 和 chat_history）
    """
    return await reset_all_sessions()


@app.post("/reset_all_sessions")
async def reset_all_sessions():
    """
    重置所有患者的会话状态（用于定时任务）
    """
    records = load_goal_reviews()
    reset_count = 0
    
    for patient_entry in records:
        if patient_entry.get("turn_index", 0) > 0 or len(patient_entry.get("chat_history", [])) > 0:
            patient_entry["turn_index"] = 0
            patient_entry["chat_history"] = []
            reset_count += 1
    
    # 保存更新后的记录
    if reset_count > 0:
        save_goal_reviews(records)
        
        print(f"Reset all sessions: {reset_count} patients reset", flush=True)
    
    return {
        "status": "ok",
        "message": f"Reset {reset_count} sessions successfully",
        "reset_count": reset_count
    }


# === Startup Background Thread ===
@app.on_event("startup")
def startup_event():
    thread = threading.Thread(target=orchestration_loop, daemon=True)
    thread.start()
