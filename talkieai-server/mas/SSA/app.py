import json
import requests
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request # type: ignore
from ai_helper import ask_ai

# === Configuration ===
SUMMARY_FILE = Path("memory/session_summaries.json")
MMA_URL = "http://mma:8000/extract"


# === Initialization ===
app = FastAPI()


# === AI Wrapper (支持OpenAI和智谱AI) ===
def ask_gpt(messages):
    """统一的AI调用接口，支持OpenAI GPT和智谱AI"""
    return ask_ai(messages, temperature=0.7)


# === Memory Handlers ===
def save_summary_to_file(patient_id, chat_history, summary):
    if SUMMARY_FILE.exists():
        with open(SUMMARY_FILE) as f:
            summaries = json.load(f)
    else:
        summaries = []

    summaries.append({
        "patient_id": patient_id,
        "chat_history": chat_history,
        "summary": summary
    })

    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_FILE, "w") as f:
        json.dump(summaries, f, indent=2)

    print(f"Session summary for {patient_id} saved", flush=True)


# === API Endpoints ===
@app.post("/trigger")
async def trigger(request: Request):
    data = await request.json()
    chat_history = data.get("chat_history", [])
    patient_id = data.get("patient_id")

    if not patient_id or not chat_history:
        return {"status": "error", "reason": "Missing patient_id or chat_history"}

    # Format chat history - 统一格式，确保与自动提取一致
    # 统一格式：每行 "Role: content"，不添加前缀，确保input一致性
    # 规范化：去除空内容，统一格式
    formatted_lines = []
    for turn in chat_history:
        role = turn.get('role', 'unknown').capitalize()
        content = turn.get('content', '').strip()
        if content:  # 只添加非空内容
            formatted_lines.append(f"{role}: {content}")
    note_text = "\n".join(formatted_lines)
    
    # 用于摘要的格式（带前缀）
    summary_input = "Here is the full conversation between the health coach and the patient:\n\n" + note_text

    # Ask GPT for summary
    messages = [
        {"role": "system", "content": "You are a summarization assistant for health coaching conversations."},
        {"role": "user", "content": summary_input}
    ]
    summary = ask_gpt(messages)
    #summary = "This is summary!"

    # Save to file
    save_summary_to_file(patient_id, chat_history, summary)

    # 自动将对话历史转换为笔记并提交给MMA进行信息提取
    try:
        # 使用统一的笔记格式（不带前缀，确保input一致性）
        
        # 构建MMA需要的笔记格式
        notes_data = [{
            "health_coach": "MAS_System",
            "study_id": patient_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "note": note_text
        }]
        
        # 提交给MMA进行提取
        mma_response = requests.post(MMA_URL, json=notes_data, timeout=30)
        if mma_response.status_code == 200:
            print(f"Successfully submitted session notes to MMA for patient {patient_id}", flush=True)
        else:
            print(f"Failed to submit notes to MMA: {mma_response.status_code} - {mma_response.text}", flush=True)
    except Exception as e:
        print(f"Error submitting notes to MMA: {e}", flush=True)
        # 不阻止SSA返回，即使MMA提取失败

    return {"status": "ok", "summary": summary}

@app.get("/summaries/{patient_id}")
async def get_summaries(patient_id: str):
    """
    获取指定患者的所有会话摘要
    """
    if not SUMMARY_FILE.exists():
        return {
            "status": "not_found",
            "patient_id": patient_id,
            "summaries": []
        }
    
    try:
        with open(SUMMARY_FILE) as f:
            all_summaries = json.load(f)
        
        # 过滤出该患者的摘要
        patient_summaries = [
            s for s in all_summaries 
            if s.get("patient_id") == patient_id
        ]
        
        return {
            "status": "ok",
            "patient_id": patient_id,
            "count": len(patient_summaries),
            "summaries": patient_summaries
        }
    except Exception as e:
        return {
            "status": "error",
            "patient_id": patient_id,
            "reason": str(e)
        }