import os


def orchestration_enabled():
    return os.getenv("OA_ORCHESTRATION_ENABLED", "true").strip().lower() == "true"


def langgraph_new_sessions_enabled():
    return os.getenv("OA_LANGGRAPH_NEW_SESSIONS_ENABLED", "false").strip().lower() == "true"


def langgraph_enabled_for_patient(patient_id):
    if not langgraph_new_sessions_enabled():
        return False
    allowlist = {
        value.strip()
        for value in os.getenv("OA_LANGGRAPH_TEST_PATIENTS", "").split(",")
        if value.strip()
    }
    return not allowlist or patient_id in allowlist
