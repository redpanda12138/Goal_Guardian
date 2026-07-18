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
    assert record == {"policy": "zero-known-vulnerabilities", "exceptions": [],
        "scope": "OA graph_v1 in-memory routing only", "checkpointer_allowed": False}

def test_compatibility_report_has_required_versions():
    report = loads((OA / "langgraph-phase1-compatibility.json").read_text(encoding="utf-8"))
    assert report["python"].startswith("3.10.")
    assert report["packages"] == {"fastapi": "0.139.0", "starlette": "1.3.1", "uvicorn": "0.51.0",
        "pydantic": "2.13.4", "httpx": "0.28.1", "langgraph": "1.2.9",
        "langgraph-checkpoint": "4.1.1", "pymysql": "1.1.2"}
