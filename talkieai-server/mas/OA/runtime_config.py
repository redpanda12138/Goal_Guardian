import os


def orchestration_enabled():
    return os.getenv("OA_ORCHESTRATION_ENABLED", "true").strip().lower() == "true"


def langgraph_new_sessions_enabled():
    return os.getenv("OA_LANGGRAPH_NEW_SESSIONS_ENABLED", "false").strip().lower() == "true"
