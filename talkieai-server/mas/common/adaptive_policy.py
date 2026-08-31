"""Content-aware stage policy. Counts pace the review; they never complete it."""
import os


MODE = "adaptive_v1"
VERSION = "oa_adaptive_v1"
CRITERIA = {
    "SOA": ("current_context", "willingness"),
    "GRA": ("selected_goal", "progress", "barriers", "next_action"),
    "SCA": ("recap", "corrections", "closure_ack"),
}
NEXT = {"SOA": "GRA", "GRA": "SCA", "SCA": "SSA"}
DEFAULT_RANGES = {"SOA": (3, 5, 7), "GRA": (5, 8, 10), "SCA": (1, 2, 3)}


def stage_range(stage):
    raw = os.getenv("OA_ADAPTIVE_" + stage + "_RANGE")
    values = tuple(int(value) for value in raw.split(",")) if raw else DEFAULT_RANGES[stage]
    if len(values) != 3 or not 1 <= values[0] <= values[1] <= values[2] <= 50:
        raise ValueError("invalid adaptive stage range")
    return values


def valid_assessment(stage, item, message_ids):
    if not isinstance(item, dict) or set(item) != {"decision", "criteria", "evidence", "reason"}:
        return False
    if type(item["decision"]) is not str or item["decision"] not in {"continue", "clarify", "advance"}:
        return False
    if not isinstance(item["reason"], str) or not 1 <= len(item["reason"]) <= 1000:
        return False
    criteria, evidence = item["criteria"], item["evidence"]
    if not isinstance(criteria, dict) or not isinstance(evidence, dict):
        return False
    if set(criteria) != set(CRITERIA[stage]) or set(evidence) != set(criteria):
        return False
    for key, complete in criteria.items():
        refs = evidence[key]
        if type(complete) is not bool or not isinstance(refs, list) or len(refs) > 20:
            return False
        if any(type(ref) is not str or ref not in message_ids for ref in refs):
            return False
        if complete and not refs:
            return False
    return True


def assess_transition(stage, count, assessment, message_ids, *, blocking=False, bounds=None):
    earliest, reference, upper = bounds or stage_range(stage)
    result = {"next_agent": stage, "reason": "continue", "needs_recovery": count >= upper}
    if blocking:
        return {**result, "reason": "pending_action", "needs_recovery": False}
    if count < earliest:
        return {**result, "reason": "before_assessment_range"}
    if not valid_assessment(stage, assessment, message_ids):
        return {**result, "reason": "invalid_assessment"}
    if not all(assessment["criteria"].values()):
        return {**result, "reason": "criteria_incomplete"}
    if assessment["decision"] == "advance":
        return {"next_agent": NEXT[stage], "reason": "stage_ready", "needs_recovery": False}
    return result
