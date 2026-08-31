"""Provider-neutral function tool definitions shared by MAS services."""
import json
from datetime import datetime


def valid_adaptive_tool_call(stage, calls):
    """Validate before OA reserves an action; the executor validates again."""
    if stage != "GRA" or not isinstance(calls, list) or len(calls) != 1 or not isinstance(calls[0], dict):
        return False
    function = calls[0].get("function")
    if not isinstance(function, dict) or not isinstance(function.get("arguments"), str):
        return False
    try:
        args = json.loads(function["arguments"])
        if not isinstance(args, dict):
            return False
        name = function.get("name")
        if name == "get_weekly_progress":
            return set(args) <= {"window"} and type(args.get("window", "5")) is str and args.get("window", "5") in {"5", "10", "all"}
        if name == "mark_goal_complete":
            return (set(args) <= {"goal_index", "note"} and type(args.get("goal_index")) is int
                and args["goal_index"] >= 0 and ("note" not in args or
                (isinstance(args["note"], str) and bool(args["note"].strip()) and len(args["note"]) <= 500)))
        if name == "reschedule_review" and set(args) == {"date"} and isinstance(args["date"], str):
            date = datetime.fromisoformat(args["date"].replace("Z", "+00:00"))
            return date.tzinfo is not None and date.utcoffset() is not None
    except (ValueError, TypeError, OverflowError):
        pass
    return False


def openai_tool_catalog():
    return [
        {
            "type": "function",
            "function": {
                "name": "get_weekly_progress",
                "description": "Read the authenticated user's weekly SMART goal progress.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window": {
                            "type": "string",
                            "enum": ["5", "10", "all"],
                            "description": "Dashboard history window.",
                        }
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mark_goal_complete",
                "description": "Mark one SMART goal complete after explicit user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "goal_index": {"type": "integer", "minimum": 0},
                        "note": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                    "required": ["goal_index"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "reschedule_review",
                "description": "Reschedule the next weekly review after explicit user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "format": "date-time",
                            "description": "Timezone-aware ISO 8601 timestamp.",
                        }
                    },
                    "required": ["date"],
                    "additionalProperties": False,
                },
            },
        },
    ]
