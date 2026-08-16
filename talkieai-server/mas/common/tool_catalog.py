"""Provider-neutral function tool definitions shared by MAS services."""


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
