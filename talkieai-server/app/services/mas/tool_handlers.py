"""Account-scoped handlers and model-facing schemas for MAS tools."""
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.mas_workflow_models import ToolName, ToolRequest, ToolResult
from app.services.mas.coach_dashboard_service import CoachDashboardService
from app.services.mas.mas_gateway_service import MASGatewayService
from app.services.mas.patient_mapping_service import PatientMappingService
from app.services.mas.tool_executor import MASToolExecutor


def build_account_tool_handlers(db: Session, account_id: str):
    async def get_weekly_progress(arguments: Dict[str, Any]) -> Dict[str, Any]:
        dashboard = await CoachDashboardService.build_dashboard(
            db, account_id, window=arguments.get("window", "5")
        )
        return {
            "weekly_progress": dashboard.get("weekly_progress", {}),
            "goals": dashboard.get("goals_detail", []),
        }

    async def mark_goal_complete(arguments: Dict[str, Any]) -> Dict[str, Any]:
        return await CoachDashboardService.apply_state_event(
            db,
            account_id,
            "goal_completed",
            arguments["goal_index"],
            arguments.get("note"),
        )

    async def reschedule_review(arguments: Dict[str, Any]) -> Dict[str, Any]:
        patient_id = PatientMappingService(db).get_or_create_patient_id(account_id)
        return await MASGatewayService.call_mas_service(
            "oa",
            "/new_sessions",
            data=[{"study_id": patient_id, "date": arguments["date"]}],
        )

    return {
        ToolName.GET_WEEKLY_PROGRESS: get_weekly_progress,
        ToolName.MARK_GOAL_COMPLETE: mark_goal_complete,
        ToolName.RESCHEDULE_REVIEW: reschedule_review,
    }


async def execute_account_tool(
    db: Session,
    account_id: str,
    request: ToolRequest,
    confirmed: bool = False,
) -> ToolResult:
    executor = MASToolExecutor(build_account_tool_handlers(db, account_id))
    return await executor.execute(request, confirmed=confirmed)


def openai_tool_catalog():
    return [
        {
            "type": "function",
            "function": {
                "name": ToolName.GET_WEEKLY_PROGRESS.value,
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
                "name": ToolName.MARK_GOAL_COMPLETE.value,
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
                "name": ToolName.RESCHEDULE_REVIEW.value,
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
