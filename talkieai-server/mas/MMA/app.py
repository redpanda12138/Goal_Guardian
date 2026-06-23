import pandas as pd
from pathlib import Path
import sys
import time, requests, json
from fastapi import FastAPI, Request, Query
from ai_helper import ask_ai, ask_ai_json
from note_utils import (
    prepare_note_for_extraction,
    merge_semantic_items,
    build_latest_goals_index,
    get_patient_goal_history,
    apply_history_pagination,
)

for common_dir in (
    Path(__file__).resolve().parent / "common",
    Path(__file__).resolve().parents[1] / "common",
):
    if common_dir.exists() and str(common_dir) not in sys.path:
        sys.path.insert(0, str(common_dir))

from mas_memory_store import load_json, save_json, memory_exists

# === Configuration ===
OA_URL = "http://oa:8000/new_sessions"
SERVICE_NAME = "mma"

SESSION_METADATA_FILE = Path("memory/session_metadata_mock.json")
SESSION_NOTES_FILE = Path("memory/session_notes_mock.json")
WEEKLY_GOALS_FILE = Path("memory/weekly_smart_goals_mock.json")
LATEST_WEEKLY_GOALS_FILE = Path("memory/latest_smart_goals.json")


# === Initialization ===
app = FastAPI()


open_tool_schema = [
    {
        "type": "function",
        "function": {
            "name": "extract_patient_info",
            "description": "Extract structured patient info from health coaching session notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "preferred_name": {"type": "string"},
                    "hobbies": {"type": "array", "items": {"type": "string"}},
                    "family": {"type": "array", "items": {"type": "string"}},
                    "friends": {"type": "array", "items": {"type": "string"}},
                    "travel": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["preferred_name", "hobbies", "family", "friends", "travel"]
            }
        }
    }
]

goal_tool_schema = [
    {
        "type": "function",
        "function": {
            "name": "extract_weekly_smart_goals",
            "description": "Extract only weekly SMART goals. Ignore long-term or monthly goals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goals": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of weekly SMART goals"
                    }
                },
                "required": ["goals"]
            }
        }
    }
]


# === GPT Wrappers ===
def extract_patient_info(note_text: str) -> dict:
    """Extract structured personal information from health coaching notes."""
    PATIENT_INFO_EXTRACTION_PROMPT = (
        "You are an expert at extracting structured information from health coaching session notes. "
        "Extract the exact parts of text, don't rephrase the text! "  
        "This is an NLU task, and not an NLG task! "      
        "For the preferred name, extract only actual first names or nicknames — do not return generic terms like "
        "'patient', 'pt', 'he', 'she', or 'client'. If a valid name cannot be found, leave the field empty. "
        "Hobbies must not include exercise or food-related activities. "
        "Avoid repeating text across family, friends, or travel fields. "
        "Include only concrete travel plans or experiences in 'travel' (not desires or dreams). "
        "If travel is family-related, keep it in 'family' and not 'travel'."
        "Always return valid JSON output. "
    )
    try:
        # 使用统一的AI调用接口，支持OpenAI和智谱AI
        # OpenAI支持工具调用，智谱AI需要直接返回JSON
        import os
        ai_server = os.getenv('AI_SERVER', 'OPENAI').upper()
        if ai_server == 'ZHIPU':
            # 为 Zhipu 提供更明确的 JSON 格式要求
            messages = [
                {"role": "system", "content": PATIENT_INFO_EXTRACTION_PROMPT + " Return ONLY valid JSON, no other text."},
                {"role": "user", "content": f"Extract structured info from:\n{note_text}\n\nReturn JSON format: {{\"preferred_name\": \"\", \"hobbies\": [], \"family\": [], \"friends\": [], \"travel\": []}}"}
            ]
            result = ask_ai_json(messages)
            return result
        else:
            # OpenAI：使用工具调用
            messages = [
                {"role": "system", "content": PATIENT_INFO_EXTRACTION_PROMPT},
                {"role": "user", "content": f"Extract structured info from:\n{note_text}"}
            ]
            response_text = ask_ai(messages, temperature=0.7, tools=open_tool_schema)
            # ask_ai已经处理了工具调用，返回JSON字符串
            return json.loads(response_text)
    except Exception as e:
        print(f"Error during patient info extraction: {e}", flush=True)
        return {
            "preferred_name": "",
            "hobbies": [],
            "family": [],
            "friends": [],
            "travel": []
        }

def extract_weekly_goals(note_text: str) -> dict:
    """Extract SMART weekly goals from coaching session notes."""
    GOAL_EXTRACTION_PROMPT = (
        "You are an expert assistant that extracts only SMART weekly goals from health coaching session notes. " 
        "Extract the exact parts of text, don't rephrase the text! "  
        "This is an NLU task, and not an NLG task! "    
        "Only include goals that are: Specific, Measurable, Achievable, Relevant, and Time-bound (SMART). "
        "Do not include vague or broad categories like 'Exercise', 'Medication', or 'Diet' unless they are written as specific SMART goals. "
        "Ignore 6-month, long-term, or vague intentions. Focus only on short-term, concrete weekly SMART goals that the patient committed to."
        "Always respond in JSON format."
    )
    try:
        import os
        if os.getenv('AI_SERVER', 'OPENAI').upper() == 'ZHIPU':
            # 智谱AI：直接要求JSON格式
            messages = [
                {"role": "system", "content": GOAL_EXTRACTION_PROMPT + " Return ONLY valid JSON, no other text."},
                {"role": "user", "content": f"Extract weekly SMART goals from the following:\n{note_text}\n\nReturn JSON format: {{\"goals\": []}}"}
            ]
            result = ask_ai_json(messages)
            return result
        else:
            # OpenAI：使用工具调用
            messages = [
                {"role": "system", "content": GOAL_EXTRACTION_PROMPT},
                {"role": "user", "content": f"Extract weekly SMART goals from the following:\n{note_text}"}
            ]
            response_text = ask_ai(messages, temperature=0.7, tools=goal_tool_schema)
            # ask_ai已经处理了工具调用，返回JSON字符串
            result = json.loads(response_text)
            # 转换为期望的格式
            if "goals" in result:
                return result
            else:
                # 如果工具调用返回的是函数参数，直接使用
                return result
    except Exception as e:
        print(f"Weekly SMART goal extraction error: {e}", flush=True)

    return {"goals": []}


# === API Endpoints ===
@app.post("/extract")
async def extract(request: Request):
    data = await request.json()
    print(f"Received {len(data)} session entries for processing.", flush=True)

    # 1. Update session metadata
    session_df = pd.DataFrame(data)[['health_coach', 'study_id', 'date']]
    existing_data = load_json(
        SERVICE_NAME, "session_metadata_mock", [], SESSION_METADATA_FILE
    )
    existing = pd.DataFrame(existing_data) if existing_data else pd.DataFrame(columns=session_df.columns)

    combined_sessions = pd.concat([existing, session_df], ignore_index=True)
    combined_sessions.drop_duplicates(subset=['study_id', 'date'], inplace=True)
    combined_sessions.sort_values(by=['study_id', 'date'], ascending=[False, False], inplace=True)

    save_json(
        SERVICE_NAME,
        "session_metadata_mock",
        combined_sessions.to_dict(orient="records"),
        SESSION_METADATA_FILE,
    )

    print(f"Session metadata updated with {len(combined_sessions)} sessions.", flush=True)

    # 2. Extract structured session notes
    patient_notes = load_json(
        SERVICE_NAME, "session_notes_mock", {}, SESSION_NOTES_FILE
    )

    for row in data:
        patient_id = row["study_id"]
        raw_note = row["note"]
        normalized_note = prepare_note_for_extraction(raw_note)
        
        if not normalized_note:
            print(f"Skipping empty note for patient {patient_id}", flush=True)
            continue
        
        # 使用规范化后的note进行提取，确保output一致性
        structured = extract_patient_info(normalized_note)
        time.sleep(1)

        for key in ["hobbies", "family", "friends", "travel"]:
            if isinstance(structured[key], str):
                structured[key] = [structured[key]] if structured[key] else []

        if patient_id not in patient_notes:
            patient_notes[patient_id] = {
                "patient_id": patient_id,
                "input": [],
                "output": {
                    "preferred_name": structured["preferred_name"],
                    "hobbies": [],
                    "family": [],
                    "friends": [],
                    "travel": []
                }
            }

        entry = patient_notes[patient_id]
        # 若新输入已经是结构化摘要，则清理旧的原始转录内容，避免 input 混杂冗长对话
        if normalized_note.startswith("Client summary:"):
            entry["input"] = [
                item for item in entry["input"]
                if "Assistant:" not in item and "User:" not in item
            ]
        # 存储规范化后的note，确保input格式一致
        if normalized_note not in entry["input"]:
            entry["input"].append(normalized_note)

        for key in ["hobbies", "family", "friends", "travel"]:
            entry["output"][key] = merge_semantic_items(
                entry["output"][key], structured[key]
            )

        if structured["preferred_name"]:
            entry["output"]["preferred_name"] = structured["preferred_name"]

    save_json(SERVICE_NAME, "session_notes_mock", patient_notes, SESSION_NOTES_FILE)

    print(f"Session notes updated with {len(patient_notes)} patients.", flush=True)

    # 3. Extract SMART goals
    smart_goals = {}
    for item in load_json(SERVICE_NAME, "weekly_smart_goals_mock", [], WEEKLY_GOALS_FILE):
        smart_goals[f"{item['patient_id']}|{item['date']}"] = item

    for row in data:
        patient_id = row["study_id"]
        date = row["date"]
        raw_note = row["note"]
        full_text = prepare_note_for_extraction(raw_note)
        
        if not full_text:
            print(f"Skipping empty note for goals extraction for patient {patient_id}", flush=True)
            continue

        # 使用规范化后的note进行提取，确保output一致性
        result = extract_weekly_goals(full_text)
        goals = result.get("goals", [])

        if goals:
            key = f"{patient_id}|{date}"
            if key not in smart_goals:
                smart_goals[key] = {
                    "patient_id": patient_id,
                    "input": full_text,
                    "date": date,
                    "output": {"goals": []}
                }
            entry = smart_goals[key]

            def clean(g): return g.strip().rstrip(".,").lower()

            existing = {clean(g) for g in entry["output"]["goals"]}
            new_goals = {clean(g) for g in goals if len(g.strip().split()) > 3}
            merged = existing.union(new_goals)

            entry["output"]["goals"] = sorted({g.capitalize() for g in merged})

        time.sleep(1)

    save_json(
        SERVICE_NAME,
        "weekly_smart_goals_mock",
        sorted(smart_goals.values(), key=lambda x: (x["patient_id"], x["date"]), reverse=True),
        WEEKLY_GOALS_FILE,
    )

    # 同步维护“每位患者最新一条目标”索引，供查询接口快速读取
    latest_goals = build_latest_goals_index(list(smart_goals.values()))
    save_json(
        SERVICE_NAME,
        "latest_smart_goals",
        latest_goals,
        LATEST_WEEKLY_GOALS_FILE,
    )

    print(f"SMART goals updated with {len(smart_goals)} entries.", flush=True)

    # 4. Notify OA with latest session dates
    latest_sessions = (
        combined_sessions.sort_values(by=["study_id", "date"], ascending=[True, False])
        .drop_duplicates(subset="study_id", keep="first")
        .to_dict(orient="records")
    )

    time.sleep(1)
    try:
        res = requests.post(OA_URL, json=latest_sessions)
        if res.status_code == 200:
            print(f"Sent {len(latest_sessions)} session entries to OA.", flush=True)
        else:
            print(f"OA responded with error: {res.status_code} - {res.text}", flush=True)
    except Exception as e:
        print(f"Error sending session metadata to OA: {e}", flush=True)

    return {
        "status": "saved",
        "sessions": len(combined_sessions),
        "patients": len(patient_notes),
        "goals": len(smart_goals)
    }

@app.get("/patient_notes/{patient_id}")
def get_notes(patient_id: str):
    notes = load_json(SERVICE_NAME, "session_notes_mock", {}, SESSION_NOTES_FILE)
    if patient_id in notes:
        print(f"Sent notes to SOA for patient {patient_id}", flush=True)
        return notes[patient_id]["output"]
    return {}

@app.get("/patient_goals/{patient_id}")
def get_goals(patient_id: str):
    if memory_exists(SERVICE_NAME, "latest_smart_goals", LATEST_WEEKLY_GOALS_FILE):
        latest_goals = load_json(
            SERVICE_NAME, "latest_smart_goals", {}, LATEST_WEEKLY_GOALS_FILE
        )
        latest = latest_goals.get(patient_id)
        recent_goals = latest.get("output", {}).get("goals", []) if latest else []
    elif memory_exists(SERVICE_NAME, "weekly_smart_goals_mock", WEEKLY_GOALS_FILE):
        all_goals = load_json(
            SERVICE_NAME, "weekly_smart_goals_mock", [], WEEKLY_GOALS_FILE
        )
        latest_index = build_latest_goals_index(all_goals)
        latest = latest_index.get(patient_id)
        recent_goals = latest.get("output", {}).get("goals", []) if latest else []
    else:
        recent_goals = []

    if not recent_goals:
        print(f"No SMART goals found for {patient_id}", flush=True)

    preferred_name = "there"
    session_data = load_json(SERVICE_NAME, "session_notes_mock", {}, SESSION_NOTES_FILE)
    preferred_name = session_data.get(patient_id, {}).get("output", {}).get("preferred_name", "there")

    print(f"Sent SMART goals to GRA for patient {patient_id}", flush=True)
    return {
        "preferred_name": preferred_name,
        "smart_goals": recent_goals
    }


@app.get("/patient_goals_history/{patient_id}")
def get_goals_history(
    patient_id: str,
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
):
    all_goals = load_json(SERVICE_NAME, "weekly_smart_goals_mock", [], WEEKLY_GOALS_FILE)

    history = get_patient_goal_history(all_goals, patient_id)
    history = apply_history_pagination(history, offset=offset, limit=limit)

    return {
        "status": "ok",
        "patient_id": patient_id,
        "offset": offset,
        "limit": limit,
        "count": len(history),
        "history": history,
    }
