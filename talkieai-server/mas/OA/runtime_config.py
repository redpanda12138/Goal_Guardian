import os


def orchestration_enabled():
    return os.getenv("OA_ORCHESTRATION_ENABLED", "true").strip().lower() == "true"
