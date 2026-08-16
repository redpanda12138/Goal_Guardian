import json
import os
import platform
from importlib.metadata import version
from pathlib import Path
from typing import TypedDict
from fastapi.testclient import TestClient
from langgraph.graph import END, StateGraph
import uvicorn
from app import app

class ProbeState(TypedDict):
    value: int

def increment(state: ProbeState) -> ProbeState:
    return {"value": state["value"] + 1}

builder = StateGraph(ProbeState)
builder.add_node("increment", increment)
builder.set_entry_point("increment")
builder.add_edge("increment", END)
compiled = builder.compile(checkpointer=None)
assert compiled.checkpointer is None
assert compiled.invoke({"value": 1}) == {"value": 2}
config = uvicorn.Config("app:app", host="127.0.0.1", port=8000)
config.load()
assert config.loaded_app is not None
with TestClient(app) as client:
    response = client.post("/trigger_agent", json={})
    assert response.status_code == 200
    assert response.json()["status"] == "error"
packages = {name: version(name) for name in ("fastapi", "starlette", "uvicorn", "pydantic", "httpx", "langgraph", "langgraph-checkpoint", "pymysql")}
assert platform.python_version().startswith("3.10.")
assert packages == {"fastapi": "0.139.0", "starlette": "1.3.1", "uvicorn": "0.51.0", "pydantic": "2.13.4", "httpx": "0.28.1", "langgraph": "1.2.9", "langgraph-checkpoint": "4.1.1", "pymysql": "1.1.2"}
Path(os.environ["OA_PHASE1_REPORT_PATH"]).write_text(json.dumps({"python": platform.python_version(), "packages": packages, "base_commit": os.environ["OA_PHASE1_BASE_COMMIT"]}, indent=2) + "\n", encoding="utf-8")
print("OA_PHASE1_RUNTIME_GATE=PASS")
