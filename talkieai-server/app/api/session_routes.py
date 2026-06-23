from fastapi import APIRouter, Depends, Response, HTTPException
import os
from sqlalchemy.orm import Session
from app.core import get_current_account
from app.core.utils import *
from app.db import get_db
from app.models.account_models import *
from app.models.response import ApiResponse
from app.services.account_service import AccountService
from app.services.chat_service import ChatService
from app.core.audio_utils import validate_audio_file

router = APIRouter()

# ========== MAS会话创建已移至 mas_routes.py ==========
# 路由：POST /api/v1/mas/sessions/create
# 这样可以避免与路径参数路由 /sessions/{session_id} 冲突


@router.get("/sessions/default")
def get_default_session(
    db: Session = Depends(get_db), account_id: str = Depends(get_current_account)
):
    """获取默认会话"""
    chat_service = ChatService(db)
    return ApiResponse(data=chat_service.get_default_session(account_id))


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account),
):
    """获取会话详情"""
    chat_service = ChatService(db)
    return ApiResponse(data=chat_service.get_session(session_id, account_id))

'''
@router.post("/sessions/{session_id}/voice-translate")
def voice_upload_api(
    session_id: str,
    dto: VoiceTranslateDTO,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account),
):
    """语音解析成文字"""
    chat_service = ChatService(db)
    return ApiResponse(data=chat_service.transform_text(session_id, dto, account_id))
'''
import logging
@router.post("/sessions/{session_id}/voice-translate")
def voice_upload_api(
    session_id: str,
    dto: VoiceTranslateDTO,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account),
):
    from app.core.whisper_voice import whisper_processor

    """使用 Whisper 模型进行语音转文字"""
    chat_service = ChatService(db)
    
    # 构建完整的音频文件路径
    audio_file_path = voice_file_get_path(dto.file_name)
    
    if not os.path.exists(audio_file_path):
        raise HTTPException(status_code=404, detail="音频文件不存在")
    
    # 验证音频文件
    if not validate_audio_file(audio_file_path):
        raise HTTPException(status_code=400, detail="音频文件无效或损坏")
    
    # 检查模型是否已初始化（与 transcribe_audio 一致：Processor+Model 或 Pipeline 任一可用即可）
    try:
        has_processor_model = getattr(whisper_processor, "processor", None) and getattr(whisper_processor, "model", None)
        if not has_processor_model and not getattr(whisper_processor, "pipe", None):
            logging.error(f"Whisper模型未初始化，无法进行转录。设备: {getattr(whisper_processor, 'device', 'Unknown')}, 模型: {getattr(whisper_processor, 'model_name', 'Unknown')}")
            return ApiResponse(data={
                "transcribed_text": "",
                "original_file": dto.file_name,
                "error": "语音识别模型未初始化，请稍后重试或联系管理员"
            })
        
        # 使用 Whisper 模型进行转录
        transcribed_text = whisper_processor.transcribe_audio(audio_file_path)
        
        if not transcribed_text:
            logging.warning(f"语音转录结果为空，文件: {dto.file_name}, 路径: {audio_file_path}")
            return ApiResponse(data={
                "transcribed_text": "",
                "original_file": dto.file_name,
                "error": "未识别到语音内容，请确保录音清晰、时长超过约 0.5 秒后重试"
            })
        
        # 返回转录结果
        return ApiResponse(data={
            "transcribed_text": transcribed_text.strip(),
            "original_file": dto.file_name
        })
    except Exception as e:
        logging.error(f"处理语音转录请求时发生异常: {e}")
        import traceback
        traceback.print_exc()
        return ApiResponse(data={
            "transcribed_text": "",
            "original_file": dto.file_name,
            "error": f"处理语音文件时出错: {str(e)}"
        })

# 新增独立的语音转文字接口，供非会话场景使用
@router.post("/voice/translate")
def standalone_voice_translate_api(
    dto: VoiceTranslateDTO,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account),
):
    """独立的语音转文字接口，不需要会话ID"""
    # 构建完整的音频文件路径
    audio_file_path = voice_file_get_path(dto.file_name)
    
    if not os.path.exists(audio_file_path):
        raise HTTPException(status_code=404, detail="音频文件不存在")
    
    # 验证音频文件
    if not validate_audio_file(audio_file_path):
        raise HTTPException(status_code=400, detail="音频文件无效或损坏")
    
    # 检查模型是否已初始化（Processor+Model 或 Pipeline 任一可用即可）
    try:
        has_processor_model = getattr(whisper_processor, "processor", None) and getattr(whisper_processor, "model", None)
        if not has_processor_model and not getattr(whisper_processor, "pipe", None):
            logging.error(f"Whisper模型未初始化，无法进行转录。设备: {getattr(whisper_processor, 'device', 'Unknown')}, 模型: {getattr(whisper_processor, 'model_name', 'Unknown')}")
            return ApiResponse(data={
                "transcribed_text": "",
                "original_file": dto.file_name,
                "error": "语音识别模型未初始化，请稍后重试或联系管理员"
            })
        
        # 使用 Whisper 模型进行转录
        transcribed_text = whisper_processor.transcribe_audio(audio_file_path)
        
        if not transcribed_text:
            logging.warning(f"语音转录结果为空(独立接口)，文件: {dto.file_name}, 路径: {audio_file_path}")
            return ApiResponse(data={
                "transcribed_text": "",
                "original_file": dto.file_name,
                "error": "未识别到语音内容，请确保录音清晰、时长超过约 0.5 秒后重试"
            })
        
        # 返回转录结果
        return ApiResponse(data={
            "transcribed_text": transcribed_text.strip(),
            "original_file": dto.file_name
        })
    except Exception as e:
        logging.error(f"处理语音转录请求时发生异常: {e}")
        import traceback
        traceback.print_exc()
        return ApiResponse(data={
            "transcribed_text": "",
            "original_file": dto.file_name,
            "error": f"处理语音文件时出错: {str(e)}"
        })

# 获取ai的第一句问候语
@router.get("/sessions/{session_id}/greeting")
def get_session_greeting(
    session_id: str,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account),
):
    """获取会话消息"""
    chat_service = ChatService(db)
    return ApiResponse(data=chat_service.get_session_greeting(session_id, account_id))


@router.post("/sessions/{session_id}/chat")
def chat_api(
    session_id: str,
    dto: ChatDTO,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account),
):
    """
    发送消息
    
    MAS模式：如果session类型为MAS，则转发到MAS服务
    原逻辑：保留原有的CHAT和TOPIC类型对话逻辑
    """
    from app.db.chat_entities import MessageSessionEntity
    
    chat_service = ChatService(db)
    
    # 检查session类型
    session = (
        db.query(MessageSessionEntity)
        .filter_by(id=session_id, account_id=account_id)
        .first()
    )
    if not session:
        return ApiResponse(code="404", status="FAILED", message="Session not found")
    
    if session.type == 'MAS':
        # ========== MAS对话模式：转发到MAS服务 ==========
        return ApiResponse(
            data=chat_service.send_mas_session_message(session_id, dto, account_id)
        )
    else:
        # ========== 原有对话逻辑（保留） ==========
        # 原有的CHAT和TOPIC类型对话逻辑
        return ApiResponse(
            data=chat_service.send_session_message(session_id, dto, account_id)
        )

# 删除最近俩次的对话
@router.delete("/sessions/{session_id}/messages/latest")
def delete_latest_session_messages(
    session_id: str,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account),
):
    """删除最近一次的对话"""
    chat_service = ChatService(db)
    return ApiResponse(
        data=chat_service.delete_latest_session_messages(session_id, account_id)
    )

# 删除session下所有的对话
@router.delete("/sessions/{session_id}/messages")
def delete_all_session_messages(
    session_id: str,
    db: Session = Depends(get_db),
    account_id: str = Depends(get_current_account),
):
    """删除最近一次的对话"""
    chat_service = ChatService(db)
    return ApiResponse(
        data=chat_service.delete_all_session_messages(session_id, account_id)
    )
