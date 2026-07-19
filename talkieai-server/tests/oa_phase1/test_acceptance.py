import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
OA = ROOT / "mas" / "OA"
ACCEPTANCE = OA / "langgraph-phase1-acceptance.json"

def test_acceptance_manifest_records_every_completed_gate():
    compatibility = json.loads((OA / "langgraph-phase1-compatibility.json").read_text(encoding="utf-8"))
    manifest = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    assert manifest == {"schema_version": 1, "phase": "oa_langgraph_phase1", "status": "passed", "base_commit": compatibility["base_commit"], "checks": {"compatibility_gate": True, "security_allowlist_gate": True, "phase1_focused_tests": True, "legacy_regression_tests": True, "scope_confinement": True}}

def test_oa_app_does_not_import_phase1_graph():
    assert "workflow_phase1" not in (OA / "app.py").read_text(encoding="utf-8")

def test_phase1_has_no_effect_or_persistence_symbols():
    source = "\n".join(path.read_text(encoding="utf-8") for path in (OA / "workflow_phase1").glob("*.py"))
    for forbidden in ("requests", "httpx", "checkpointer.postgres", "psycopg", "msgpack", "saver", "serializer", "database", "mas_memory_store", "receive_user_message", "receive_message", "trigger_agent"):
        assert forbidden not in source

def test_six_service_topology_is_unchanged():
    compose = yaml.safe_load((ROOT / "mas" / "docker-compose.yml").read_text(encoding="utf-8"))
    assert set(compose["services"]) == {"mma", "soa", "gra", "sca", "ssa", "oa"}

def test_langgraph_is_confined_to_oa():
    allowed = {OA / "requirements.txt", OA / "requirements-langgraph-phase1-candidate.txt", OA / "requirements-langgraph-phase1-probe.txt", OA / "requirements-langgraph-phase1.lock", ROOT / "requirements-mas-checkpoint-probe.txt"}
    offenders = [path for path in ROOT.rglob("requirements*.txt") if "langgraph" in path.read_text(encoding="utf-8").lower() and path not in allowed]
    assert offenders == []
