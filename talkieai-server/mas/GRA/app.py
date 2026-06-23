from pathlib import Path
import sys
import requests, json, threading
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
MMA_URL = "http://mma:8000/patient_goals"
OA_URL = "http://oa:8000/receive_message"
OA_USER_URL = "http://oa:8000/receive_user_message"
SCA_URL = "http://oa:8000/trigger_agent"

MEMORY_FILE = Path("/app/memory/gra_conversations.json")
SERVICE_NAME = "gra"


# === Initialization ===
app = FastAPI()


# === AI Wrapper (支持OpenAI和智谱AI) ===
def ask_gpt(messages):
    """统一的AI调用接口，支持OpenAI GPT和智谱AI"""
    return ask_ai(messages, temperature=0.7)


# === Goal Selection Helper ===
def extract_goal_from_input(user_input: str, smart_goals: list) -> tuple[str, bool]:
    if not smart_goals:
        return ("", False)
    
    import re
    user_input_lower = user_input.strip().lower()
    
    # 方法1: 检查是否是数字（如"1"、"1."等）
    number_match = re.search(r'(\d+)', user_input)
    if number_match:
        goal_index = int(number_match.group(1)) - 1
        if 0 <= goal_index < len(smart_goals):
            print(f"Matched goal by number: {goal_index + 1} -> {smart_goals[goal_index]}", flush=True)
            return (smart_goals[goal_index], True)
    
    # 检查英文序数词（"first", "second", "third"等）
    ordinal_words = {
        "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
        "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10
    }
    for word, num in ordinal_words.items():
        if word in user_input_lower or f"the {word}" in user_input_lower or f"the {word} one" in user_input_lower:
            goal_index = num - 1
            if 0 <= goal_index < len(smart_goals):
                print(f"Matched goal by ordinal word '{word}': {smart_goals[goal_index]}", flush=True)
                return (smart_goals[goal_index], True)
    
    # 方法2: 检查是否包含目标文本（部分匹配）
    for i, goal in enumerate(smart_goals):
        goal_lower = goal.lower()
        # 提取关键词（4个字符以上的词）
        goal_words = set(re.findall(r'\b\w{4,}\b', goal_lower))
        user_words = set(re.findall(r'\b\w{4,}\b', user_input_lower))
        
        # 检查是否有足够的关键词匹配
        common_words = goal_words.intersection(user_words)
        if len(common_words) >= 2:  # 至少2个关键词匹配
            print(f"Matched goal by text similarity: '{goal}' (matched words: {common_words})", flush=True)
            return (goal, True)
        
        # 检查是否包含目标的主要部分
        if len(goal_lower) > 5:
            goal_core = re.sub(r'[^\w\s]', '', goal_lower)
            if goal_core in user_input_lower or user_input_lower in goal_core:
                print(f"Matched goal by substring: '{goal}'", flush=True)
                return (goal, True)
    
    # 方法3: 使用AI辅助理解
    print(f"Could not match goal directly, using AI to interpret: '{user_input}'", flush=True)
    goal_list = "\n".join([f"{i+1}. {g}" for i, g in enumerate(smart_goals)])
    ai_prompt = [
        {"role": "system", "content": "You are a helpful assistant that extracts goal selections from user input. Respond with ONLY the goal number (1, 2, 3, etc.) or the exact goal text."},
        {"role": "user", "content": f"User said: '{user_input}'\n\nAvailable goals:\n{goal_list}\n\nWhich goal does the user want to review? Respond with ONLY the number (1-{len(smart_goals)}) or the exact goal text."}
    ]
    try:
        ai_response = ask_gpt(ai_prompt).strip()
        print(f"AI interpretation: '{ai_response}'", flush=True)
        
        # 尝试从AI响应中提取数字
        number_match = re.search(r'(\d+)', ai_response)
        if number_match:
            goal_num = int(number_match.group(1))
            if 1 <= goal_num <= len(smart_goals):
                print(f"AI matched goal by number: {goal_num} -> {smart_goals[goal_num - 1]}", flush=True)
                return (smart_goals[goal_num - 1], True)
        
        # 尝试匹配目标文本
        for goal in smart_goals:
            if goal.lower() in ai_response.lower() or ai_response.lower() in goal.lower():
                print(f"AI matched goal by text: '{goal}'", flush=True)
                return (goal, True)
    except Exception as e:
        print(f"Error in AI goal extraction: {e}", flush=True)
    
    # 如果所有方法都失败，返回原始输入
    print(f"Could not extract goal, using original input: '{user_input}'", flush=True)
    return (user_input.strip(), False)


def is_positive_response(user_input: str) -> bool:
    """
    判断用户回复是否是肯定的（yes/no）
    返回: True表示肯定，False表示否定
    """
    import re
    user_input_lower = user_input.strip().lower()
    
    positive_responses = [
        "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "alright", "of course",
        "absolutely", "definitely", "certainly", "indeed", "correct", "right"
    ]
    
    negative_responses = [
        "no", "nope", "nah", "not", "don't", "won't", "can't", "cannot"
    ]
    
    # 检查否定回复
    for neg in negative_responses:
        if neg in user_input_lower:
            return False
    
    # 检查肯定回复
    for pos in positive_responses:
        if pos in user_input_lower:
            return True
    
    # 如果包含"want"、"would like"等表达意愿的词，认为是肯定的
    if re.search(r'\b(want|would like|interested|willing|ready)\b', user_input_lower):
        return True
    
    # 默认返回False（如果无法确定，保守处理）
    return False


# === Memory Handlers ===
def load_memory():
    return load_json(SERVICE_NAME, "gra_conversations", [], MEMORY_FILE)

def save_message(new_record):
    records = load_memory()

    updated = False
    for existing in records:
        if existing.get("patient_id") == new_record.get("patient_id"):
            if "chat_history" in new_record:
                existing["chat_history"] = new_record["chat_history"]
            if "selected_goal" in new_record:
                existing["selected_goal"] = new_record["selected_goal"]
            updated = True
            break

    if not updated:
        records.append(new_record)

    save_json(SERVICE_NAME, "gra_conversations", records, MEMORY_FILE)


# === API Endpoints ===
@app.post("/trigger")
async def trigger(request: Request):
    data = await request.json()
    patient_id = data.get("patient_id")
    turn_index = data.get("turn_index")

    if not patient_id:
        return {"status": "error", "reason": "Missing patient_id"}

    print(f"GRA was triggered to do weekly SMART goal review for patient {patient_id}", flush=True)

    try:
        response = requests.get(f"{MMA_URL}/{patient_id}")
        if response.status_code == 200:
            response_data = response.json()
            print(f"Retrieved {response_data} from MMA for patient {patient_id}", flush=True)
        else:
            print(f"Failed to fetch SMART goals from MMA: {response.status_code}", flush=True)
            return {"status": "failed", "reason": "MMA fetch error"}
    except Exception as e:
        print(f"Error contacting MMA: {e}", flush=True)
        return {"status": "failed", "reason": str(e)}

    preferred_name = response_data.get("preferred_name")
    smart_goals = response_data.get("smart_goals", [])

    system_prompt = "You are a warm, empathetic health coach helping a patient review their SMART goals."

    if smart_goals:
        goal_list = "\n".join([f"{i+1}. {g}" for i, g in enumerate(smart_goals)])
        user_prompt = (
            f"Turn {turn_index}. The patient's name is {preferred_name}. Their SMART goals are:\n{goal_list}\n\n"
            "Remind them of these goals and ask which one they'd like to review during this session. Do not greet them."
        )
    else:
        user_prompt = (
            f"Turn {turn_index}. The patient's name is {preferred_name}. No SMART goals were set in their last session.\n\n"
            "Let them know that no goals were set and ask if they'd like to set some with their health coach. "
            "Say that you can’t help set goals—only review them."
        )

    initial_prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # GPT generation placeholder
    assistant_reply = ask_gpt(initial_prompt)
    #assistant_reply = "Let's review your goals from the last session."
    chat_history = [{"role": "assistant", "content": assistant_reply}]

    save_message({
        "patient_id": patient_id,
        "chat_history": chat_history,
        "smart_goals": smart_goals
    })

    # 同步发送消息到OA，确保turn_index正确更新
    try:
        oa_response = requests.post(OA_URL, json={
            "patient_id": patient_id,
            "turn_index": turn_index,
            "message": assistant_reply
        }, timeout=5)
        if oa_response.status_code == 200:
            print(f"Sent HC message to OA for patient {patient_id} (turn {turn_index})", flush=True)
        else:
            print(f"Failed to send message to OA (status {oa_response.status_code})", flush=True)
    except Exception as e:
        print(f"Failed to notify OA: {e}", flush=True)

    return {"status": "GRA triggered", "patient_id": patient_id}

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
    
    # 检查是否已经处理过这个turn_index的用户消息，避免重复处理
    # 计算当前应该有多少条user消息（turn_index条，因为turn_index从1开始）
    user_messages = [msg for msg in chat_history if msg.get("role") == "user"]
    expected_user_count = turn_index  # turn_index=6意味着应该有6条user消息
    
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

    turn_index += 1

    # 获取smart_goals状态
    smart_goals = patient_entry.get("smart_goals", [])
    has_goals = smart_goals and len(smart_goals) > 0

    # 智能识别目标选择（turn 7）
    if turn_index == 7:
        if has_goals:
            # 有目标：智能识别用户选择的目标
            selected_goal, is_valid = extract_goal_from_input(user_input, smart_goals)
            patient_entry["selected_goal"] = selected_goal
            
            if not is_valid:
                print(f"Warning: Could not clearly identify goal from '{user_input}', using: '{selected_goal}'", flush=True)
        else:
            # 没有目标：识别用户是否同意设置目标
            is_positive = is_positive_response(user_input)
            if is_positive:
                # 用户同意设置目标，但GRA不能设置，所以结束GRA流程，触发SCA
                print(f"Patient wants to set goals, but GRA cannot set goals. Ending GRA and triggering SCA.", flush=True)
                patient_entry["selected_goal"] = "wants_to_set_goals"
                selected_goal = "wants_to_set_goals"
                # 直接触发SCA，跳过后续的目标审查流程
                try:
                    oa_response = requests.post(SCA_URL, json={
                        "patient_id": patient_id,
                        "turn_index": turn_index,
                        "agent_to_trigger": "SCA"
                    })
                    if oa_response.status_code == 200:
                        print(f"Triggered SCA for patient {patient_id} (no goals, wants to set)", flush=True)
                    else:
                        print(f"Failed to trigger SCA (status {oa_response.status_code})", flush=True)
                except Exception as e:
                    print(f"Error triggering SCA: {e}", flush=True)
                
                # 保存并返回
                save_message({
                    "patient_id": patient_id,
                    "chat_history": chat_history,
                    "selected_goal": selected_goal
                })
                return {"status": "message processed", "turn_index": turn_index, "action": "triggered_sca"}
            else:
                # 用户不想设置目标，结束GRA流程，触发SCA
                print(f"Patient does not want to set goals. Ending GRA and triggering SCA.", flush=True)
                patient_entry["selected_goal"] = "no_goals_set"
                selected_goal = "no_goals_set"
                # 直接触发SCA
                try:
                    oa_response = requests.post(SCA_URL, json={
                        "patient_id": patient_id,
                        "turn_index": turn_index,
                        "agent_to_trigger": "SCA"
                    })
                    if oa_response.status_code == 200:
                        print(f"Triggered SCA for patient {patient_id} (no goals, declined)", flush=True)
                    else:
                        print(f"Failed to trigger SCA (status {oa_response.status_code})", flush=True)
                except Exception as e:
                    print(f"Error triggering SCA: {e}", flush=True)
                
                # 保存并返回
                save_message({
                    "patient_id": patient_id,
                    "chat_history": chat_history,
                    "selected_goal": selected_goal
                })
                return {"status": "message processed", "turn_index": turn_index, "action": "triggered_sca"}
    else:
        selected_goal = patient_entry.get("selected_goal", "your selected goal")

    assistant_prompt = ""
    if turn_index == 7:
        # 只有在有目标的情况下才会执行到这里
        if has_goals:
            assistant_prompt = f'The client chose the goal: "{selected_goal}". Ask about their positive experience with it. Don\'t use client name if available.'
        # 如果没有目标，已经在上面处理并返回了
    elif turn_index == 8:
        assistant_prompt = f'Reflect warmly on the client\'s positive experience. Then ask: What was the most rewarding or enjoyable part of working on "{selected_goal}" last week? Don\'t mention goal explicitly, but rephrase it.'
    elif turn_index == 9:
        assistant_prompt = f'Encourage deeper reflection. Ask about any challenges they faced with "{selected_goal}", and what they learned about themselves while working through those. Don\'t use client name if available. Don\'t mention goal explicitly, but rephrase it.'
    elif turn_index == 10:
        assistant_prompt = f'Acknowledge their efforts so far. Then ask: How would you rate your success with "{selected_goal}" on a scale from 0% to 100%? Don\'t use client name if available. Don\'t mention goal explicitly, but rephrase it.'
    elif turn_index == 11:
        assistant_prompt = f'Reflect gently on the percentage they shared. Follow up with: What made you choose that number? Don\'t mention goal explicitly, but rephrase it.'
    elif turn_index == 12:
        assistant_prompt = f'Affirm the client’s reflections and thank them. End with an encouraging statement. Do not ask additional questions. Don\'t mention goal explicitly, but rephrase it.'

    assistant_reply = ""
    if turn_index < 13:
        full_prompt = [
                {"role": "system", "content": "You are a warm, empathetic health coach helping a patient review their SMART goals."},
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
    elif turn_index == 13 or turn_index == 14:
        # turn_index=13 是 GRA 的最后一个 turn，触发 SCA
        # 注意：收到 turn_index=13 的消息后，第285行已经执行 turn_index += 1，所以此时 turn_index 已经是 14
        # 所以这里需要同时检查 turn_index == 13 和 turn_index == 14，以确保能触发 SCA
        agent_to_trigger = "SCA"
        try:
            oa_response = requests.post(SCA_URL, json={
                "patient_id": patient_id,
                "turn_index": turn_index,
                "agent_to_trigger": agent_to_trigger
            })
            if oa_response.status_code == 200:
                print(f"Triggered {agent_to_trigger} for patient {patient_id} (turn {turn_index})", flush=True)
                # 等待一下，确保SCA的消息已经到达OA并更新turn_index
                import time
                time.sleep(0.5)
            else:
                print(f"Failed to trigger {agent_to_trigger} for patient {patient_id} (status {oa_response.status_code})", flush=True)
        except Exception as e:
            print(f"Error triggering {agent_to_trigger} for patient {patient_id}: {e}", flush=True)
    elif turn_index > 14:
        # turn_index > 14 应该由 SCA 处理，GRA 不应该再处理
        print(f"Warning: GRA received turn_index {turn_index} > 14, this should be handled by SCA. Skipping.", flush=True)
        # 直接保存用户消息，不生成回复

    save_message({
        "patient_id": patient_id,
        "chat_history": chat_history,
        "selected_goal": selected_goal
    })

    return {"status": "message processed", "turn_index": turn_index}
