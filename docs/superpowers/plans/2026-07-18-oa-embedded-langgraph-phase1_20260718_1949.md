# OA-Embedded LangGraph Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate an OA-local in-memory LangGraph router matching canonical completion-first legacy decisions, without production integration.

**Architecture:** A typed parity router feeds a no-checkpointer graph. An external Python 3.10 probe gates compatibility and security; artifacts are evidence only.

## Global Constraints

- Keep the six-service topology; confine LangGraph to OA.
- Phase 1 must not modify `mas/OA/Dockerfile` or any production `requirements.txt`; Phase 2 may decide whether to consume the evidence lock after renewed review.
- Use Python 3.10 for the compatibility gate and the OA runtime.
- The historical `langgraph==0.2.28` candidate is affected by GHSA-g48c-2wqr-h844. It may proceed only under the project-maintainer exception, reviewed before Phase 2 or 30 September 2026, whichever is earlier.
- Compile and invoke with `checkpointer=None`; do not import savers, serializers, Psycopg 3, msgpack hooks, or any persistent checkpointer package.
- State is ephemeral, validated, JSON-compatible data with no clients, sessions, objects, callables, responses, secrets, or binary values.
- Do not alter callback writes, import the graph into live code, or add dispatch, retrieval, tools, persistence, or later-phase behavior.
- Use completion-first parity: turn 15 or completed selects no Agent; active turns 0..5 select SOA, 6..13 GRA, and 14 SCA. Preserve the older turn-6 discrepancy in `mas_routes.py` and OA status output.

---

### Task 1: Clean Python 3.10 OA Dependency, Runtime, and Security Gate

- [ ] **Step 1: Write the scoped test bootstrap, resolver inputs, exception, and failing confinement tests**

```python
from json import loads
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OA = ROOT / "mas" / "OA"
BANNED = {"langgraph-checkpoint-postgres", "psycopg", "psycopg-binary", "psycopg-pool"}

def active_lines(path):
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]

def test_oa_phase1_lock_is_exact_and_excludes_persistence_packages():
    lines = active_lines(OA / "requirements-langgraph-phase1.lock")
    assert lines
    assert all("==" in line for line in lines)
    assert not any(line.split("==", 1)[0].lower() in BANNED for line in lines)

def test_security_exception_is_bounded():
    record = loads((OA / "langgraph-phase1-security-exception.json").read_text(encoding="utf-8"))
    assert record == {
        "advisory": "GHSA-g48c-2wqr-h844",
        "candidate": "langgraph==0.2.28",
        "owner": "project maintainer",
        "review_deadline": "2026-09-30",
        "scope": "OA graph_v1 in-memory routing only",
        "checkpointer_allowed": False,
    }

def test_compatibility_report_has_required_versions():
    report = loads((OA / "langgraph-phase1-compatibility.json").read_text(encoding="utf-8"))
    assert report["python"].startswith("3.10.")
    assert set(report["packages"]) == {"fastapi", "uvicorn", "pydantic", "httpx",
                                       "langgraph", "langchain-core", "langgraph-checkpoint"}
    assert report["packages"]["pydantic"] == "1.10.15"
    assert report["packages"]["httpx"] == "0.25.0"
```

```python
# tests/oa_phase1/conftest.py
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVER / "mas" / "OA"))
sys.path.insert(0, str(SERVER / "mas" / "common"))
```

```text
# requirements-langgraph-phase1-candidate.txt
-r requirements.txt
pydantic==1.10.15
httpx==0.25.0
langgraph==0.2.28
langchain-core==0.2.43
langgraph-checkpoint==1.0.12

# requirements-langgraph-phase1-probe.txt
pytest==8.3.5
pip-audit==2.9.0
```

- [ ] **Step 2: Create the clean external environment and verify RED**

Run from the repository root in Windows PowerShell 5.1:

```powershell
$ProbeRoot = Join-Path $env:TEMP "goalguardian-oa-langgraph-phase1-py310"
if (Test-Path -LiteralPath $ProbeRoot) { throw "Probe directory already exists; stop without deleting or reusing it: $ProbeRoot" }
py -3.10 -m venv $ProbeRoot
$ProbePython = Join-Path $ProbeRoot "Scripts\python.exe"
& $ProbePython --version
if ($LASTEXITCODE -ne 0) { throw "CPython 3.10 is required" }
& $ProbePython -m pip install --upgrade pip==24.3.1
& $ProbePython -m pip install -r talkieai-server\mas\OA\requirements-langgraph-phase1-candidate.txt
if ($LASTEXITCODE -ne 0) { throw "runtime candidate install failed" }
$Phase1BaseCommit = git rev-parse HEAD
$TempLock = Join-Path $ProbeRoot "requirements-langgraph-phase1.lock"
$FreezeLines = & $ProbePython -m pip freeze --exclude pip --exclude setuptools --exclude wheel | Sort-Object
[System.IO.File]::WriteAllLines($TempLock, [string[]]$FreezeLines, (New-Object System.Text.UTF8Encoding($false)))
& $ProbePython -m pip install -r talkieai-server\mas\OA\requirements-langgraph-phase1-probe.txt
if ($LASTEXITCODE -ne 0) { throw "probe tooling install failed" }
& $ProbePython -m pytest -q talkieai-server\tests\oa_phase1\test_dependency_gate.py
```

Expected: Python 3.10; RED because evidence files are absent. Installation failure stops the plan.

- [ ] **Step 3: Add the runtime and audit-verification scripts**

```json
{"advisory":"GHSA-g48c-2wqr-h844","candidate":"langgraph==0.2.28","owner":"project maintainer","review_deadline":"2026-09-30","scope":"OA graph_v1 in-memory routing only","checkpointer_allowed":false}
```

```python
# scripts/probe_langgraph_phase1_runtime.py
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
packages = {name: version(name) for name in
            ("fastapi", "uvicorn", "pydantic", "httpx", "langgraph",
             "langchain-core", "langgraph-checkpoint")}
assert platform.python_version().startswith("3.10.")
assert packages["pydantic"] == "1.10.15"
assert packages["httpx"] == "0.25.0"
assert packages["langgraph"] == "0.2.28"
Path(os.environ["OA_PHASE1_REPORT_PATH"]).write_text(json.dumps({
    "python": platform.python_version(), "packages": packages,
    "base_commit": os.environ["OA_PHASE1_BASE_COMMIT"],
}, indent=2) + "\n", encoding="utf-8")
print("OA_PHASE1_RUNTIME_GATE=PASS")
```

```python
# scripts/verify_langgraph_phase1_audit.py
import json, sys
ALLOWED = {"GHSA-g48c-2wqr-h844", "CVE-2026-28277", "PYSEC-2026-83"}
payload = json.load(open(sys.argv[1], encoding="utf-8"))
for dependency in payload["dependencies"]:
    for vuln in dependency.get("vulns", []):
        identifiers = {vuln["id"], *vuln.get("aliases", [])}
        permitted = (dependency["name"].lower() == "langgraph"
                     and dependency["version"] == "0.2.28"
                     and "GHSA-g48c-2wqr-h844" in identifiers
                     and identifiers <= ALLOWED)
        if not permitted:
            raise SystemExit(f"unapproved advisory: {dependency['name']} {identifiers}")
print("OA_PHASE1_AUDIT_GATE=PASS")
```

- [ ] **Step 4: Run every gate using temporary outputs**

Run from the repository root in the same PowerShell process:

```powershell
$TempReport = Join-Path $ProbeRoot "langgraph-phase1-compatibility.json"
$AuditReport = Join-Path $ProbeRoot "pip-audit.json"
& $ProbePython -m pip check
if ($LASTEXITCODE -ne 0) { throw "pip check failed" }
$env:PYTHONPATH="talkieai-server\mas\OA;talkieai-server\mas\common"
$env:OA_ORCHESTRATION_ENABLED="false"
$env:OA_PHASE1_REPORT_PATH=$TempReport
$env:OA_PHASE1_BASE_COMMIT=$Phase1BaseCommit
& $ProbePython talkieai-server\mas\OA\scripts\probe_langgraph_phase1_runtime.py
if ($LASTEXITCODE -ne 0) { throw "runtime probe failed" }
& $ProbePython -m pip_audit -r $TempLock -f json -o $AuditReport
if ($LASTEXITCODE -gt 1) { throw "pip-audit execution failed" }
& $ProbePython talkieai-server\mas\OA\scripts\verify_langgraph_phase1_audit.py $AuditReport
if ($LASTEXITCODE -ne 0) { throw "audit allowlist failed" }
```

Expected: both PASS markers. GHSA-g48c-2wqr-h844, CVE-2026-28277, and PYSEC-2026-83 are aliases for the same governed LangGraph 0.2.28 exception; anything else stops the plan.

- [ ] **Step 5: Publish evidence only after the complete gate, then run Phase 1 tests with Python 3.10**

```powershell
Copy-Item -LiteralPath $TempLock -Destination talkieai-server\mas\OA\requirements-langgraph-phase1.lock
Copy-Item -LiteralPath $TempReport -Destination talkieai-server\mas\OA\langgraph-phase1-compatibility.json
& $ProbePython -m pytest -q talkieai-server\tests\oa_phase1
if ($LASTEXITCODE -ne 0) { throw "Phase 1 tests failed" }
```

Expected: PASS; production install files remain unchanged. Retain the external environment.

- [ ] **Step 6: Commit the passing gate**

```bash
git add -- talkieai-server/mas/OA/requirements-langgraph-phase1-candidate.txt talkieai-server/mas/OA/requirements-langgraph-phase1-probe.txt talkieai-server/mas/OA/requirements-langgraph-phase1.lock talkieai-server/mas/OA/langgraph-phase1-security-exception.json talkieai-server/mas/OA/langgraph-phase1-compatibility.json talkieai-server/mas/OA/scripts/probe_langgraph_phase1_runtime.py talkieai-server/mas/OA/scripts/verify_langgraph_phase1_audit.py talkieai-server/tests/oa_phase1/conftest.py talkieai-server/tests/oa_phase1/test_dependency_gate.py
git diff --cached --name-only
git commit -m "build: gate OA LangGraph phase one runtime"
```

### Task 2: OA-Local Graph State and Route Decision Contracts

- [ ] **Step 1: Write failing contract tests**

```python
import pytest
from workflow_phase1.contracts import validate_graph_input

VALID = {
    "patient_id": "p-1", "session_generation": 2,
    "workflow_version": "oa_graph_v1", "request_id": "r-1",
    "event_type": "user_turn", "turn_index": 6, "session_status": "active",
}

def test_validate_graph_input_returns_json_safe_state():
    state = validate_graph_input({
        "patient_id": "p-1", "session_generation": 2,
        "workflow_version": "oa_graph_v1", "request_id": "r-1",
        "event_type": "user_turn", "turn_index": 6, "session_status": "active",
    })
    assert state["turn_index"] == 6

def test_validate_graph_input_rejects_binary_and_out_of_range():
    with pytest.raises(ValueError, match="JSON-compatible"):
        validate_graph_input({**VALID, "patient_id": b"p-1"})
    with pytest.raises(ValueError, match="between 0 and 15"):
        validate_graph_input({**VALID, "turn_index": 16})

@pytest.mark.parametrize("patch,message", [
    ({"turn_index": True}, "turn_index"),
    ({"event_type": "model_decides"}, "event_type"),
    ({"session_status": "unknown"}, "session_status"),
    ({"session_generation": 0}, "session_generation"),
    ({"patient_id": ""}, "patient_id"),
    ({"requested_agent": "MMA", "event_type": "agent_transition_intent"}, "requested_agent"),
    ({"unexpected": "value"}, "unknown graph field"),
    ({"request_id": lambda: None}, "JSON-compatible"),
])
def test_validate_graph_input_rejects_strict_boundary_violations(patch, message):
    with pytest.raises(ValueError, match=message):
        validate_graph_input({**VALID, **patch})
```

- [ ] **Step 2: Verify the tests fail**

Run: `& $ProbePython -m pytest -q talkieai-server\tests\oa_phase1\test_contracts.py`

Expected: FAIL because `workflow_phase1.contracts` does not exist.

- [ ] **Step 3: Implement minimal typed contracts and strict validation**

```python
import json
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional, TypedDict

AgentName = Literal["SOA", "GRA", "SCA", "SSA"]
EventType = Literal["user_turn", "agent_transition_intent", "scheduled_start"]
RouteStatus = Literal["ready", "completed", "error"]

class RequiredGraphState(TypedDict):
    patient_id: str
    session_generation: int
    workflow_version: str
    request_id: str
    event_type: EventType
    turn_index: int
    session_status: Literal["active", "completed"]

class GraphState(RequiredGraphState, total=False):
    requested_agent: AgentName
    selected_agent: AgentName
    route_reason: str
    route_status: RouteStatus
    error_category: str

@dataclass(frozen=True)
class RouteDecision:
    selected_agent: Optional[AgentName]
    route_reason: str
    route_status: RouteStatus

def validate_graph_input(raw: Mapping[str, Any]) -> GraphState:
    required = {"patient_id", "session_generation", "workflow_version", "request_id",
                "event_type", "turn_index", "session_status"}
    allowed = required | {"requested_agent"}
    if required - set(raw):
        raise ValueError("missing required graph field")
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unknown graph field: {sorted(unknown)[0]}")
    try:
        json.dumps(raw, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("graph input must contain JSON-compatible values") from error
    for field in ("patient_id", "workflow_version", "request_id", "event_type", "session_status"):
        if type(raw[field]) is not str or not raw[field]:
            raise ValueError(f"{field} must be a non-empty string")
    if type(raw["session_generation"]) is not int or raw["session_generation"] < 1:
        raise ValueError("session_generation must be a positive integer")
    if type(raw["turn_index"]) is not int or not 0 <= raw["turn_index"] <= 15:
        raise ValueError("turn_index must be between 0 and 15")
    if raw["workflow_version"] != "oa_graph_v1":
        raise ValueError("unsupported workflow_version")
    if raw["event_type"] not in {"user_turn", "agent_transition_intent", "scheduled_start"}:
        raise ValueError("unsupported event_type")
    if raw["session_status"] not in {"active", "completed"}:
        raise ValueError("unsupported session_status")
    requested = raw.get("requested_agent")
    if requested is not None and requested not in {"SOA", "GRA", "SCA", "SSA"}:
        raise ValueError("unsupported requested_agent")
    if raw["event_type"] == "agent_transition_intent" and requested is None:
        raise ValueError("requested_agent is required for transition intent")
    return dict(raw)  # type: ignore[return-value]

def decision_from_state(state: GraphState) -> RouteDecision:
    return RouteDecision(state.get("selected_agent"), state["route_reason"], state["route_status"])
```

- [ ] **Step 4: Run the focused suite**

Run: `& $ProbePython -m pytest -q talkieai-server\tests\oa_phase1\test_contracts.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -- talkieai-server/mas/OA/workflow_phase1/__init__.py talkieai-server/mas/OA/workflow_phase1/contracts.py talkieai-server/tests/oa_phase1/test_contracts.py
git diff --cached --name-only
git commit -m "feat: define OA graph phase one contracts"
```

### Task 3: Completion-First Canonical Parity Router

- [ ] **Step 1: Write failing golden boundary tests**

```python
import pytest
from workflow_phase1.contracts import RouteDecision
from workflow_phase1.parity import decide_legacy_parity, select_active_agent

BASE = {
    "patient_id": "p-1", "session_generation": 1,
    "workflow_version": "oa_graph_v1", "request_id": "r-1",
    "event_type": "user_turn", "turn_index": 0, "session_status": "active",
}

@pytest.mark.parametrize("turn,agent", [(0,"SOA"),(5,"SOA"),(6,"GRA"),(13,"GRA"),(14,"SCA")])
def test_active_boundaries_match_canonical_selector(turn, agent):
    assert select_active_agent(turn) == agent

def test_completion_guard_precedes_selector():
    state = {**BASE, "turn_index": 15, "session_status": "completed"}
    assert decide_legacy_parity(state) == RouteDecision(None, "session_completed", "completed")
```

- [ ] **Step 2: Verify failure**

Run: `& $ProbePython -m pytest -q talkieai-server\tests\oa_phase1\test_parity.py`

Expected: FAIL because the parity functions are undefined.

- [ ] **Step 3: Implement completion-first routing**

```python
from .contracts import AgentName, GraphState, RouteDecision

def select_active_agent(turn_index: int) -> AgentName:
    if type(turn_index) is not int or not 0 <= turn_index <= 14:
        raise ValueError("active turn_index must be between 0 and 14")
    if turn_index <= 5:
        return "SOA"
    if turn_index <= 13:
        return "GRA"
    return "SCA"

def decide_legacy_parity(state: GraphState) -> RouteDecision:
    if state["turn_index"] == 15 or state["session_status"] == "completed":
        return RouteDecision(None, "session_completed", "completed")
    agent = select_active_agent(state["turn_index"])
    return RouteDecision(agent, "canonical_legacy_parity", "ready")
```

- [ ] **Step 4: Prove parity and preserve the characterised discrepancy**

Run Phase 1 parity with the probe interpreter: `& $ProbePython -m pytest -q talkieai-server\tests\oa_phase1\test_parity.py`

Run the existing legacy characterization separately: `& talkieai-server\myenv\Scripts\python.exe -m pytest -q talkieai-server\tests\test_legacy_mas_routing.py`

Expected: PASS with the documented turn-6 discrepancy.

- [ ] **Step 5: Commit**

```bash
git add -- talkieai-server/mas/OA/workflow_phase1/parity.py talkieai-server/tests/oa_phase1/test_parity.py
git diff --cached --name-only
git commit -m "feat: add completion-first OA parity router"
```

### Task 4: Pure In-Memory LangGraph Skeleton

- [ ] **Step 1: Write failing graph tests**

```python
import pytest
from pathlib import Path
from workflow_phase1.graph import build_phase1_graph, invoke_phase1_graph

BASE = {
    "patient_id": "p-1", "session_generation": 1,
    "workflow_version": "oa_graph_v1", "request_id": "r-1",
    "event_type": "user_turn", "turn_index": 0, "session_status": "active",
}

def test_graph_has_no_checkpointer():
    graph = build_phase1_graph()
    assert graph.checkpointer is None

@pytest.mark.parametrize("turn,expected", [(0,"SOA"),(6,"GRA"),(14,"SCA"),(15,None)])
def test_every_boundary_terminates(turn, expected):
    decision = invoke_phase1_graph({**BASE, "turn_index": turn,
        "session_status": "completed" if turn == 15 else "active"})
    assert decision.selected_agent == expected

def test_invalid_and_transition_paths_terminate_without_side_effects():
    invalid = invoke_phase1_graph({**BASE, "turn_index": True})
    assert (invalid.route_status, invalid.selected_agent) == ("error", None)
    approved = invoke_phase1_graph({**BASE, "event_type": "agent_transition_intent",
                                    "turn_index": 6, "requested_agent": "GRA"})
    assert (approved.route_status, approved.selected_agent) == ("ready", "GRA")
    conflict = invoke_phase1_graph({**BASE, "event_type": "agent_transition_intent",
                                    "turn_index": 6, "requested_agent": "SCA"})
    assert (conflict.route_status, conflict.selected_agent) == ("error", None)

def test_workflow_source_is_pure():
    package = Path(__file__).resolve().parents[2] / "mas" / "OA" / "workflow_phase1"
    source = "\n".join(path.read_text(encoding="utf-8") for path in package.glob("*.py"))
    for forbidden in ("requests", "httpx", "mas_memory_store", "psycopg",
                      "msgpack", "receive_message", "trigger_agent"):
        assert forbidden not in source
```

- [ ] **Step 2: Verify failure**

Run: `& $ProbePython -m pytest -q talkieai-server\tests\oa_phase1\test_graph.py`

Expected: FAIL because the graph module does not exist.

- [ ] **Step 3: Implement pure nodes and deterministic edges**

```python
from typing import Any, Mapping
from langgraph.graph import END, StateGraph
from .contracts import GraphState, RouteDecision, decision_from_state, validate_graph_input
from .parity import decide_legacy_parity

def validate_event(state: GraphState) -> GraphState:
    try:
        return validate_graph_input(state)
    except ValueError as error:
        return {**state, "route_status": "error", "route_reason": "invalid_event",
                "error_category": str(error)}

def after_validation(state: GraphState) -> str:
    return "invalid" if state.get("route_status") == "error" else "valid"

def classify_session(state: GraphState) -> GraphState:
    if state["turn_index"] == 15 or state["session_status"] == "completed":
        return {**state, "route_status": "completed", "route_reason": "session_completed"}
    return state

def select_route(state: GraphState) -> GraphState:
    decision = decide_legacy_parity(state)
    return {**state, "selected_agent": decision.selected_agent,
            "route_reason": decision.route_reason, "route_status": decision.route_status}

def emit_completed(state: GraphState) -> GraphState:
    result = dict(state)
    result.pop("selected_agent", None)
    return {**result, "route_reason": "session_completed", "route_status": "completed"}

def after_classification(state: GraphState) -> str:
    if state.get("route_status") == "completed":
        return "completed"
    return "transition" if state["event_type"] == "agent_transition_intent" else "active"

def validate_transition_intent(state: GraphState) -> GraphState:
    expected = decide_legacy_parity(state)
    if state.get("requested_agent") != expected.selected_agent:
        return {**state, "route_status": "error", "route_reason": "transition_conflict"}
    return {**state, "selected_agent": expected.selected_agent,
            "route_status": "ready", "route_reason": "transition_approved"}

def emit_route_error(state: GraphState) -> GraphState:
    result = dict(state)
    result.pop("selected_agent", None)
    return {**result, "route_status": "error",
            "route_reason": state.get("route_reason", "invalid_event")}

def build_phase1_graph():
    builder = StateGraph(GraphState)
    builder.add_node("validate_event", validate_event)
    builder.add_node("classify_session", classify_session)
    builder.add_node("select_legacy_parity_route", select_route)
    builder.add_node("validate_transition_intent", validate_transition_intent)
    builder.add_node("emit_completed", emit_completed)
    builder.add_node("emit_route_error", emit_route_error)
    builder.set_entry_point("validate_event")
    builder.add_conditional_edges("validate_event", after_validation,
        {"invalid": "emit_route_error", "valid": "classify_session"})
    builder.add_conditional_edges("classify_session", after_classification,
        {"completed": "emit_completed", "active": "select_legacy_parity_route",
         "transition": "validate_transition_intent"})
    builder.add_edge("emit_completed", END)
    builder.add_edge("emit_route_error", END)
    builder.add_edge("select_legacy_parity_route", END)
    builder.add_conditional_edges("validate_transition_intent",
        lambda state: "error" if state["route_status"] == "error" else "ready",
        {"error": "emit_route_error", "ready": END})
    return builder.compile(checkpointer=None)

def invoke_phase1_graph(raw: Mapping[str, Any]) -> RouteDecision:
    graph = build_phase1_graph()
    assert graph.checkpointer is None
    return decision_from_state(graph.invoke(dict(raw)))
```

- [ ] **Step 4: Run topology and purity checks**

Run: `& $ProbePython -m pytest -q talkieai-server\tests\oa_phase1\test_graph.py talkieai-server\tests\oa_phase1\test_parity.py`

Expected: PASS; every path terminates and the graph remains pure with no checkpointer.

- [ ] **Step 5: Commit**

```bash
git add -- talkieai-server/mas/OA/workflow_phase1/graph.py talkieai-server/tests/oa_phase1/test_graph.py
git diff --cached --name-only
git commit -m "feat: compile pure OA LangGraph phase one skeleton"
```

### Task 5: Topology, Security Boundary, and Full Legacy Regression Gate

- [ ] **Step 1: Write acceptance tests with a deliberately missing manifest**

```python
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
OA = ROOT / "mas" / "OA"
ACCEPTANCE = OA / "langgraph-phase1-acceptance.json"

def test_acceptance_manifest_records_every_completed_gate():
    compatibility = json.loads((OA / "langgraph-phase1-compatibility.json").read_text(encoding="utf-8"))
    manifest = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    assert manifest == {
        "schema_version": 1, "phase": "oa_langgraph_phase1", "status": "passed",
        "base_commit": compatibility["base_commit"],
        "checks": {"compatibility_gate": True, "security_allowlist_gate": True,
                   "phase1_focused_tests": True, "legacy_regression_tests": True,
                   "scope_confinement": True},
    }

def test_oa_app_does_not_import_phase1_graph():
    source = (OA / "app.py").read_text(encoding="utf-8")
    assert "workflow_phase1" not in source

def test_phase1_has_no_effect_or_persistence_symbols():
    source = "\n".join(path.read_text(encoding="utf-8") for path in
        (OA / "workflow_phase1").glob("*.py"))
    for forbidden in ("requests", "httpx", "checkpointer.postgres", "psycopg",
                      "msgpack", "saver", "serializer", "database", "mas_memory_store",
                      "receive_user_message", "receive_message", "trigger_agent"):
        assert forbidden not in source

def test_six_service_topology_is_unchanged():
    compose = yaml.safe_load((ROOT / "mas" / "docker-compose.yml").read_text(encoding="utf-8"))
    assert set(compose["services"]) == {"mma", "soa", "gra", "sca", "ssa", "oa"}

def test_langgraph_is_confined_to_oa():
    allowed = {OA / "requirements-langgraph-phase1-candidate.txt",
               OA / "requirements-langgraph-phase1-probe.txt",
               OA / "requirements-langgraph-phase1.lock"}
    requirement_files = list(ROOT.rglob("requirements*.txt"))
    offenders = [path for path in requirement_files
                 if "langgraph" in path.read_text(encoding="utf-8").lower()
                 and path not in allowed]
    assert offenders == []
```

- [ ] **Step 2: Observe real RED from the missing manifest**

```powershell
& $ProbePython -m pytest -q talkieai-server\tests\oa_phase1\test_acceptance.py
```

Expected: only the manifest test FAILS with `FileNotFoundError`; the source, topology, and confinement tests pass.

- [ ] **Step 3: Run verification before recording acceptance**

```powershell
& $ProbePython -m pytest -q talkieai-server\tests\oa_phase1\test_dependency_gate.py talkieai-server\tests\oa_phase1\test_contracts.py talkieai-server\tests\oa_phase1\test_parity.py talkieai-server\tests\oa_phase1\test_graph.py
if ($LASTEXITCODE -ne 0) { throw "focused Phase 1 gate failed" }
Push-Location talkieai-server
& .\myenv\Scripts\python.exe -m pytest -q tests --ignore=tests/oa_phase1
$LegacyExit = $LASTEXITCODE
Pop-Location
if ($LegacyExit -ne 0) { throw "legacy regression gate failed" }
```

Expected: both commands PASS; Phase 1 introduces no skip or expected failure.

- [ ] **Step 4: Create the complete acceptance manifest**

```powershell
$Compatibility = Get-Content -Raw talkieai-server\mas\OA\langgraph-phase1-compatibility.json | ConvertFrom-Json
$Phase1BaseCommit = $Compatibility.base_commit
if ([string]::IsNullOrWhiteSpace($Phase1BaseCommit)) { throw "compatibility report has no base_commit" }
$Acceptance = [ordered]@{ schema_version=1; phase="oa_langgraph_phase1"; status="passed"; base_commit=$Phase1BaseCommit; checks=[ordered]@{ compatibility_gate=$true; security_allowlist_gate=$true; phase1_focused_tests=$true; legacy_regression_tests=$true; scope_confinement=$true } }
[System.IO.File]::WriteAllText("talkieai-server\mas\OA\langgraph-phase1-acceptance.json", (($Acceptance | ConvertTo-Json -Depth 4) + [Environment]::NewLine), (New-Object System.Text.UTF8Encoding($false)))
```

- [ ] **Step 5: Verify GREEN, stage exactly, and commit**

```powershell
& $ProbePython -m pytest -q talkieai-server\tests\oa_phase1
if ($LASTEXITCODE -ne 0) { throw "complete Phase 1 suite failed" }
git add -- talkieai-server/mas/OA/langgraph-phase1-acceptance.json talkieai-server/tests/oa_phase1/test_acceptance.py
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "staged whitespace check failed" }
git diff --cached --name-only
git commit -m "test: enforce OA LangGraph phase one boundaries"
if ($LASTEXITCODE -ne 0) { throw "Task 5 commit failed" }
```

- [ ] **Step 6: Verify the exact scope across all five commits**

```powershell
$Compatibility = Get-Content -Raw talkieai-server\mas\OA\langgraph-phase1-compatibility.json | ConvertFrom-Json
$Phase1BaseCommit = $Compatibility.base_commit
git cat-file -e "$Phase1BaseCommit^{commit}"
if ($LASTEXITCODE -ne 0) { throw "invalid recorded base commit" }
git diff --check "$Phase1BaseCommit..HEAD"
if ($LASTEXITCODE -ne 0) { throw "five-commit whitespace check failed" }
$ActualPaths = @(git diff --name-only "$Phase1BaseCommit..HEAD" | Sort-Object)
$AllowedPaths = @(
"talkieai-server/mas/OA/langgraph-phase1-acceptance.json", "talkieai-server/mas/OA/langgraph-phase1-compatibility.json", "talkieai-server/mas/OA/langgraph-phase1-security-exception.json",
"talkieai-server/mas/OA/requirements-langgraph-phase1-candidate.txt", "talkieai-server/mas/OA/requirements-langgraph-phase1-probe.txt", "talkieai-server/mas/OA/requirements-langgraph-phase1.lock",
"talkieai-server/mas/OA/scripts/probe_langgraph_phase1_runtime.py", "talkieai-server/mas/OA/scripts/verify_langgraph_phase1_audit.py",
"talkieai-server/mas/OA/workflow_phase1/__init__.py", "talkieai-server/mas/OA/workflow_phase1/contracts.py", "talkieai-server/mas/OA/workflow_phase1/graph.py", "talkieai-server/mas/OA/workflow_phase1/parity.py",
"talkieai-server/tests/oa_phase1/conftest.py", "talkieai-server/tests/oa_phase1/test_acceptance.py", "talkieai-server/tests/oa_phase1/test_contracts.py", "talkieai-server/tests/oa_phase1/test_dependency_gate.py", "talkieai-server/tests/oa_phase1/test_graph.py", "talkieai-server/tests/oa_phase1/test_parity.py") | Sort-Object
$ScopeDelta = @(Compare-Object -ReferenceObject $AllowedPaths -DifferenceObject $ActualPaths)
if ($ScopeDelta.Count -ne 0) { throw "Phase 1 path set differs from exact allowlist" }
$CommitCount = [int](git rev-list --count "$Phase1BaseCommit..HEAD")
if ($CommitCount -ne 5) { throw "expected exactly five Phase 1 commits; found $CommitCount" }
git status --short
```

Expected: exactly 18 allowed paths and five commits; no `Dockerfile`, production requirements, integration file, or topology file changed.

Phase 1 ends after this commit. Do not start OA ingress, feature-flag, live effect-executor, callback-reservation, rollout, RAG, tool, or checkpoint work under this plan.
