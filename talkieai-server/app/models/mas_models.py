"""
MAS系统相关的数据模型
"""
from pydantic import BaseModel, StrictInt, validator
from typing import Optional, List, Dict, Any

from app.models.mas_workflow_models import ToolRequest


class SubmitNotesDTO(BaseModel):
    """提交健康教练会话笔记"""
    notes: List[Dict[str, Any]]  # 会话笔记列表


class SendMessageDTO(BaseModel):
    """发送消息到当前代理"""
    user_input: str
    turn_index: int


class TriggerSessionDTO(BaseModel):
    """触发会话"""
    patient_id: Optional[str] = None  # 可选，默认使用当前用户


class CreateScheduleDTO(BaseModel):
    """创建预约"""
    notes: List[Dict[str, Any]]  # 预约数据列表


class DeleteMasSessionsDTO(BaseModel):
    """批量删除未完成的 MAS 会话（仅 completed=0）"""
    session_ids: List[str]


class CoachStateEventDTO(BaseModel):
    """Coach 快捷动作：更新本地进度并写入状态消息"""
    event_type: str  # goal_completed | goal_skipped | progress_refreshed
    goal_index: Optional[int] = None
    note: Optional[str] = None
    message: Optional[str] = None


class ExecuteWorkflowToolDTO(BaseModel):
    """Authenticated execution request for one allowlisted workflow tool."""

    tool_request: ToolRequest
    confirmed: bool = False
    turn_index: Optional[StrictInt] = None

    @validator("turn_index")
    def validate_turn_index(cls, value):
        if value is not None and (type(value) is not int or not 0 <= value <= 15):
            raise ValueError("turn_index must be between 0 and 15")
        return value


class ResolveWorkflowToolConfirmationDTO(BaseModel):
    """Resolve one server-owned workflow-tool confirmation action."""

    action_id: str
    confirmed: bool

    @validator("action_id")
    def validate_action_id(cls, value):
        if not isinstance(value, str) or not value.strip() or len(value) > 80:
            raise ValueError("action_id must be a non-empty stable identifier")
        return value.strip()


class AdaptiveSessionControlDTO(BaseModel):
    session_id: str
    session_generation: StrictInt
    command: str

    @validator("command")
    def validate_command(cls, value):
        if value not in {"pause", "resume", "extend", "stop", "skip"}:
            raise ValueError("Unsupported session control")
        return value
