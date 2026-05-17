"""
MAS系统API路由：作为网关转发请求到MAS服务
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from typing import Optional
from app.core import get_current_account
from app.db import get_db
from app.models.response import ApiResponse
from app.models.mas_models import (
    SubmitNotesDTO,
    SendMessageDTO,
    TriggerSessionDTO,
    CreateScheduleDTO,
    DeleteMasSessionsDTO,
    CoachStateEventDTO,
)
from app.services.mas.patient_mapping_service import PatientMappingService
from app.services.mas.mas_gateway_service import MASGatewayService
from app.core.logging import logging

router = APIRouter()

# ========== MAS会话管理 ==========

@router.post("/mas/sessions/create", name="Create MAS Session")
async def create_mas_session(
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account)
):
    """
    创建MAS健康教练会话（已废弃，建议使用get_or_create）
    
    将account_id转换为patient_id，然后创建MAS类型的session
    """
    try:
        from app.services.chat_service import ChatService
        chat_service = ChatService(db)
        result = chat_service.create_mas_session(account_id)
        return ApiResponse(data=result)
    except Exception as e:
        logging.error(f"Create MAS session error: {e}")
        return ApiResponse(code="500", status="FAILED", message=str(e))

@router.get("/mas/sessions/get-or-create", name="Get or Create MAS Session")
async def get_or_create_mas_session(
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account)
):
    """
    获取或创建MAS健康教练会话
    
    优先返回用户最新的MAS会话，如果没有则创建一个新的
    这样可以保持聊天记录的连续性
    """
    try:
        from app.services.chat_service import ChatService
        chat_service = ChatService(db)
        result = chat_service.get_or_create_mas_session(account_id)
        return ApiResponse(data=result)
    except Exception as e:
        logging.error(f"Get or create MAS session error: {e}")
        return ApiResponse(code="500", status="FAILED", message=str(e))


@router.get("/mas/sessions/list", name="List MAS Sessions")
async def list_mas_sessions(
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account)
):
    """
    获取当前用户所有 MAS 会话列表（历史对话），按创建时间倒序
    用于聊天页历史记录侧栏
    """
    try:
        from app.services.chat_service import ChatService
        chat_service = ChatService(db)
        result = chat_service.get_mas_sessions_list(account_id)
        return ApiResponse(data=result)
    except Exception as e:
        logging.error(f"List MAS sessions error: {e}")
        return ApiResponse(code="500", status="FAILED", message=str(e))


@router.post("/mas/sessions/delete-bulk", name="Delete incomplete MAS sessions")
async def delete_mas_sessions_bulk(
    dto: DeleteMasSessionsDTO,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account),
):
    """批量删除未完成的 MAS 会话及关联消息（message_session.completed=0）。"""
    try:
        from app.services.chat_service import ChatService

        chat_service = ChatService(db)
        result = chat_service.delete_mas_sessions_bulk(account_id, dto.session_ids)
        return ApiResponse(data=result)
    except Exception as e:
        logging.error(f"Delete MAS sessions error: {e}")
        return ApiResponse(code="500", status="FAILED", message=str(e))


# ========== 患者信息管理 ==========

@router.post("/mas/patients/notes", name="Submit Session Notes")
async def submit_notes(
    dto: SubmitNotesDTO,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account)
):
    """
    提交健康教练会话笔记，触发MMA提取
    
    将account_id转换为patient_id，然后转发到MMA服务
    """
    try:
        mapping_service = PatientMappingService(db)
        patient_id = mapping_service.get_or_create_patient_id(account_id)
        
        # 转换数据格式：添加patient_id到每个笔记
        notes_data = []
        for note in dto.notes:
            note_data = note.copy()
            note_data["study_id"] = patient_id
            notes_data.append(note_data)
        
        # 调用MMA服务
        result = await MASGatewayService.call_mas_service(
            "mma",
            "/extract",
            data=notes_data
        )
        
        return ApiResponse(data=result)
    except Exception as e:
        logging.error(f"Submit notes error: {e}")
        return ApiResponse(code="500", status="FAILED", message=str(e))


@router.get("/mas/patients/info", name="Get Patient Info")
async def get_patient_info(
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account)
):
    """
    获取患者结构化信息
    
    从MMA服务获取患者信息
    如果数据不存在，尝试从对话历史中自动提取
    """
    try:
        mapping_service = PatientMappingService(db)
        patient_id = mapping_service.get_or_create_patient_id(account_id)
        
        result = await MASGatewayService.call_mas_service(
            "mma",
            f"/patient_notes/{patient_id}",
            method="GET"
        )
        
        # 总是检查对话历史是否有更新，如果有新消息则触发提取
        try:
            # 获取对话历史
            history_data = await MASGatewayService.call_mas_service(
                "oa",
                f"/conversation_history/{patient_id}",
                method="GET"
            )
            
            # 如果有对话历史，检查是否需要更新
            if history_data.get("status") == "ok" and history_data.get("chat_history"):
                chat_history = history_data["chat_history"]
                if len(chat_history) > 0:
                    # 检查对话历史中是否有user消息（说明是新对话）
                    has_user_messages = any(msg.get("role") == "user" for msg in chat_history)
                    
                    # 如果对话历史包含user消息，或者MMA中没有数据，则触发提取
                    should_extract = (
                        has_user_messages or  # 有新对话（包含user消息）
                        not result or  # MMA中没有数据
                        (isinstance(result, dict) and len(result) == 0) or  # MMA返回空
                        not result.get("preferred_name")  # MMA中没有preferred_name
                    )
                    
                    if should_extract:
                        # 将对话历史转换为笔记格式（统一格式，与SSA保持一致）
                        # 规范化：去除空内容，统一格式
                        formatted_lines = []
                        for msg in chat_history:
                            role = msg.get('role', 'unknown').capitalize()
                            content = msg.get('content', '').strip()
                            if content:  # 只添加非空内容
                                formatted_lines.append(f"{role}: {content}")
                        note_text = "\n".join(formatted_lines)
                        
                        # 提交给MMA进行提取
                        from datetime import datetime
                        notes_data = [{
                            "health_coach": "MAS_System",
                            "study_id": patient_id,
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "note": note_text
                        }]
                        
                        # 异步提交，不阻塞返回
                        try:
                            await MASGatewayService.call_mas_service(
                                "mma",
                                "/extract",
                                data=notes_data
                            )
                            logging.info(f"Auto-extracted patient info for {patient_id} from conversation history (has_user_messages={has_user_messages})")
                        except Exception as extract_error:
                            logging.warning(f"Failed to auto-extract patient info: {extract_error}")
                        
                        # 重新获取提取后的数据
                        result = await MASGatewayService.call_mas_service(
                            "mma",
                            f"/patient_notes/{patient_id}",
                            method="GET"
                        )
        except Exception as auto_extract_error:
            logging.warning(f"Auto-extraction failed: {auto_extract_error}")
        
        # 如果仍然为空，返回默认结构
        if not result or (isinstance(result, dict) and len(result) == 0):
            result = {
                "preferred_name": "",
                "hobbies": [],
                "family": [],
                "friends": [],
                "travel": []
            }
        
        return ApiResponse(data=result)
    except Exception as e:
        logging.error(f"Get patient info error: {e}")
        # 返回空数据而不是错误，让前端可以正常显示
        return ApiResponse(data={
            "preferred_name": "",
            "hobbies": [],
            "family": [],
            "friends": [],
            "travel": []
        })


@router.get("/mas/patients/goals", name="Get Patient Goals")
async def get_patient_goals(
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account)
):
    """
    获取患者SMART目标
    
    从MMA服务获取患者的目标
    如果数据不存在，尝试从对话历史中自动提取
    """
    try:
        mapping_service = PatientMappingService(db)
        patient_id = mapping_service.get_or_create_patient_id(account_id)
        
        result = await MASGatewayService.call_mas_service(
            "mma",
            f"/patient_goals/{patient_id}",
            method="GET"
        )
        
        # 总是检查对话历史是否有更新，如果有新消息则触发提取
        try:
            # 获取对话历史
            history_data = await MASGatewayService.call_mas_service(
                "oa",
                f"/conversation_history/{patient_id}",
                method="GET"
            )
            
            # 如果有对话历史，检查是否需要更新
            if history_data.get("status") == "ok" and history_data.get("chat_history"):
                chat_history = history_data["chat_history"]
                if len(chat_history) > 0:
                    # 检查对话历史中是否有user消息（说明是新对话）
                    has_user_messages = any(msg.get("role") == "user" for msg in chat_history)
                    
                    # 如果对话历史包含user消息，或者MMA中没有目标，则触发提取
                    should_extract = (
                        has_user_messages or  # 有新对话（包含user消息）
                        not result or  # MMA中没有数据
                        not result.get("smart_goals") or  # MMA中没有目标
                        len(result.get("smart_goals", [])) == 0  # MMA中目标为空
                    )
                    
                    if should_extract:
                        # 将对话历史转换为笔记格式（统一格式，与SSA保持一致）
                        # 规范化：去除空内容，统一格式
                        formatted_lines = []
                        for msg in chat_history:
                            role = msg.get('role', 'unknown').capitalize()
                            content = msg.get('content', '').strip()
                            if content:  # 只添加非空内容
                                formatted_lines.append(f"{role}: {content}")
                        note_text = "\n".join(formatted_lines)
                        
                        # 提交给MMA进行提取
                        from datetime import datetime
                        notes_data = [{
                            "health_coach": "MAS_System",
                            "study_id": patient_id,
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "note": note_text
                        }]
                        
                        # 异步提交，不阻塞返回
                        try:
                            await MASGatewayService.call_mas_service(
                                "mma",
                                "/extract",
                                data=notes_data
                            )
                            logging.info(f"Auto-extracted patient goals for {patient_id} from conversation history (has_user_messages={has_user_messages})")
                        except Exception as extract_error:
                            logging.warning(f"Failed to auto-extract patient goals: {extract_error}")
                        
                        # 重新获取提取后的数据
                        result = await MASGatewayService.call_mas_service(
                            "mma",
                            f"/patient_goals/{patient_id}",
                            method="GET"
                        )
        except Exception as auto_extract_error:
            logging.warning(f"Auto-extraction failed: {auto_extract_error}")
        
        # 确保返回正确的数据结构
        if not result:
            result = {
                "preferred_name": "",
                "smart_goals": []
            }
        elif isinstance(result, dict) and "smart_goals" not in result:
            result["smart_goals"] = []
        
        return ApiResponse(data=result)
    except Exception as e:
        logging.error(f"Get patient goals error: {e}")
        # 返回空数据而不是错误，让前端可以正常显示
        return ApiResponse(data={
            "preferred_name": "",
            "smart_goals": []
        })


@router.get("/mas/patients/next_review_time", name="Get Patient Next Review Time")
async def get_patient_next_review_time(
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account)
):
    """
    获取患者下一次 OA 预约时间。
    - 如果该预约已触发，则返回 `next_review_time=None`
    """
    try:
        mapping_service = PatientMappingService(db)
        patient_id = mapping_service.get_or_create_patient_id(account_id)

        result = await MASGatewayService.call_mas_service(
            "oa",
            f"/next_review_time/{patient_id}",
            method="GET"
        )
        return ApiResponse(data=result)
    except Exception as e:
        logging.error(f"Get next review time error: {e}")
        return ApiResponse(data={"next_review_time": None, "triggered": False})


# ========== Coach 看板聚合 ==========


@router.get("/mas/coach/dashboard", name="Coach Dashboard")
async def get_coach_dashboard(
    window: str = "5",
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account),
):
    """聚合 SMART 目标、周进度、今日计划、下次运动推算、回访与会话状态（供 Home/Coach/Chat 共用）。"""
    try:
        from app.services.mas.coach_dashboard_service import CoachDashboardService

        data = await CoachDashboardService.build_dashboard(
            db, account_id, window=window
        )
        return ApiResponse(data=data)
    except Exception as e:
        logging.error(f"Coach dashboard error: {e}")
        return ApiResponse(code="500", status="FAILED", message=str(e))


@router.post("/mas/coach/goals/state-event", name="Coach Goal State Event")
async def post_coach_goal_state_event(
    dto: CoachStateEventDTO,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account),
):
    """快捷动作更新 sys_cache 进度账本，并写入一条 STATE_EVENT 系统消息。"""
    try:
        from app.services.chat_service import ChatService
        from app.services.mas.coach_dashboard_service import CoachDashboardService

        state_result = await CoachDashboardService.apply_state_event(
            db, account_id, dto.event_type, dto.goal_index, dto.note
        )
        if not state_result.get("ok"):
            return ApiResponse(
                code="400",
                status="FAILED",
                message=state_result.get("reason") or "Invalid coach state event",
                data=state_result,
            )
        chat_service = ChatService(db)
        style = f"STATE_EVENT:{dto.event_type}"
        if dto.event_type == "goal_completed" and dto.goal_index is not None:
            content = f"状态更新：目标 {dto.goal_index + 1} 已标记为完成。"
        elif dto.event_type == "goal_skipped":
            content = dto.message or "状态更新：已跳过该目标。"
        else:
            content = dto.message or "状态更新：进度已刷新。"
        chat_service.add_mas_state_event_message(account_id, content, style)
        dashboard = await CoachDashboardService.build_dashboard(
            db, account_id, window="5"
        )
        return ApiResponse(data={"dashboard": dashboard})
    except Exception as e:
        logging.error(f"Coach state event error: {e}")
        return ApiResponse(code="500", status="FAILED", message=str(e))


# ========== 会话管理 ==========

@router.post("/mas/sessions/trigger", name="Trigger Session")
async def trigger_session(
    dto: TriggerSessionDTO,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account)
):
    """
    手动触发健康教练会话（SOA）
    
    如果提供了patient_id，使用提供的；否则使用当前用户的patient_id
    """
    try:
        mapping_service = PatientMappingService(db)
        if dto.patient_id:
            patient_id = dto.patient_id
        else:
            patient_id = mapping_service.get_or_create_patient_id(account_id)
        
        result = await MASGatewayService.call_mas_service(
            "soa",
            "/trigger",
            data={"patient_id": patient_id, "turn_index": 1}
        )
        
        return ApiResponse(data=result)
    except Exception as e:
        logging.error(f"Trigger session error: {e}")
        return ApiResponse(code="500", status="FAILED", message=str(e))


@router.post("/mas/sessions/message", name="Send Message")
async def send_message(
    dto: SendMessageDTO,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account)
):
    """
    发送消息到当前代理
    
    根据turn_index判断当前是哪个代理（SOA/GRA/SCA），然后转发消息
    这里简化处理：依次尝试SOA、GRA、SCA，直到成功
    """
    try:
        mapping_service = PatientMappingService(db)
        patient_id = mapping_service.get_or_create_patient_id(account_id)
        
        message_data = {
            "patient_id": patient_id,
            "user_input": dto.user_input,
            "turn_index": dto.turn_index
        }
        
        # 根据turn_index判断代理
        # SOA: turn_index 1-6
        # GRA: turn_index 7-13
        # SCA: turn_index 14-15
        if dto.turn_index <= 6:
            # 尝试SOA
            try:
                result = await MASGatewayService.call_mas_service(
                    "soa",
                    "/receive_message",
                    data=message_data
                )
                return ApiResponse(data=result)
            except Exception as e:
                logging.warning(f"SOA message failed, trying other agents: {e}")
        
        if dto.turn_index <= 13:
            # 尝试GRA
            try:
                result = await MASGatewayService.call_mas_service(
                    "gra",
                    "/receive_message",
                    data=message_data
                )
                return ApiResponse(data=result)
            except Exception as e:
                logging.warning(f"GRA message failed, trying SCA: {e}")
        
        # 尝试SCA
        result = await MASGatewayService.call_mas_service(
            "sca",
            "/receive_message",
            data=message_data
        )
        return ApiResponse(data=result)
        
    except Exception as e:
        logging.error(f"Send message error: {e}")
        return ApiResponse(code="500", status="FAILED", message=str(e))


@router.get("/mas/sessions/current", name="Get Current Session")
async def get_current_session(
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account)
):
    """
    获取当前会话状态
    
    从OA获取会话状态（需要OA提供此接口）
    """
    try:
        mapping_service = PatientMappingService(db)
        patient_id = mapping_service.get_or_create_patient_id(account_id)
        
        # 从OA获取会话状态
        result = await MASGatewayService.call_mas_service(
            "oa",
            f"/session_status/{patient_id}",
            method="GET"
        )
        return ApiResponse(data=result)
    except Exception as e:
        logging.error(f"Get current session error: {e}")
        return ApiResponse(code="500", status="FAILED", message=str(e))


@router.get("/mas/sessions/history", name="Get Conversation History")
async def get_conversation_history(
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account)
):
    """
    获取完整的对话历史
    
    从OA的goal_reviews.json获取该患者的所有对话记录
    """
    try:
        mapping_service = PatientMappingService(db)
        patient_id = mapping_service.get_or_create_patient_id(account_id)
        
        # 从OA获取对话历史
        result = await MASGatewayService.call_mas_service(
            "oa",
            f"/conversation_history/{patient_id}",
            method="GET"
        )
        return ApiResponse(data=result)
    except Exception as e:
        logging.error(f"Get conversation history error: {e}")
        return ApiResponse(code="500", status="FAILED", message=str(e))


@router.get("/mas/sessions/summaries", name="Get Session Summaries")
async def get_session_summaries(
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account)
):
    """
    获取会话摘要列表
    
    从SSA获取该患者的所有会话摘要
    """
    try:
        mapping_service = PatientMappingService(db)
        patient_id = mapping_service.get_or_create_patient_id(account_id)
        
        # 从SSA获取会话摘要
        result = await MASGatewayService.call_mas_service(
            "ssa",
            f"/summaries/{patient_id}",
            method="GET"
        )
        return ApiResponse(data=result)
    except Exception as e:
        logging.error(f"Get session summaries error: {e}")
        return ApiResponse(code="500", status="FAILED", message=str(e))


# ========== 预约管理 ==========

@router.post("/mas/schedules", name="Create Schedule")
async def create_schedule(
    dto: CreateScheduleDTO,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account)
):
    """
    创建/更新预约（通知OA）
    
    将预约数据发送到OA服务
    """
    try:
        mapping_service = PatientMappingService(db)
        patient_id = mapping_service.get_or_create_patient_id(account_id)
        
        # 转换数据格式：添加patient_id
        # - 若有 date：按预约时间触发
        # - 若无 date：OA 侧按“7天后9点”默认策略处理
        schedule_data = []
        if not dto.notes:
            schedule_data.append({"study_id": patient_id})
        else:
            for note in dto.notes:
                schedule_entry = {"study_id": patient_id}
                if note.get("date"):
                    schedule_entry["date"] = note.get("date")
                schedule_data.append(schedule_entry)
        
        result = await MASGatewayService.call_mas_service(
            "oa",
            "/new_sessions",
            data=schedule_data
        )
        
        return ApiResponse(data=result)
    except Exception as e:
        logging.error(f"Create schedule error: {e}")
        return ApiResponse(code="500", status="FAILED", message=str(e))


# ========== 健康检查 ==========

@router.get("/mas/health", name="Check MAS Services Health")
async def check_mas_health():
    """
    检查所有MAS服务的健康状态
    """
    services = ["mma", "soa", "gra", "sca", "ssa", "oa"]
    health_status = {}
    
    for service in services:
        try:
            is_healthy = await MASGatewayService.check_service_health(service)
            health_status[service] = {
                "status": "healthy" if is_healthy else "unhealthy",
                "url": MASGatewayService.get_service_url(service) or "N/A"
            }
        except Exception as e:
            health_status[service] = {
                "status": "error",
                "error": str(e),
                "url": MASGatewayService.get_service_url(service) or "N/A"
            }
    
    all_healthy = all(
        status.get("status") == "healthy" 
        for status in health_status.values()
    )
    
    return ApiResponse(
        data=health_status,
        status="SUCCESS" if all_healthy else "PARTIAL",
        message="所有服务健康" if all_healthy else "部分服务不可用"
    )
