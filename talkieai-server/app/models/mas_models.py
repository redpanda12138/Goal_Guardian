"""
MAS系统相关的数据模型
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


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
