from enum import Enum
from typing import List, Dict

from pydantic import BaseModel, constr


class MessageType(Enum):
    """消息类型"""

    ACCOUNT = "ACCOUNT"
    SYSTEM = "SYSTEM"


class WechatLoginDTO(BaseModel):
    code: str = None
    state: str = None


class VisitorLoginDTO(BaseModel):
    fingerprint: constr(min_length=15)

class LoginDTO(BaseModel):
    username: str
    password: str

class RegisterDTO(BaseModel):
    username: str
    password: str

class UpdateRoleDTO(BaseModel):
    role: str


class AccountInfo(BaseModel):
    account_id: str
    username: str | None = None
    patient_id: str | None = None
    today_chat_count: int
    total_chat_count: int
    target_language_label: str


class ChatDTO(BaseModel):
    """聊天"""

    message: str | None = None
    file_name: str | None = None


class MessagePracticeDTO(BaseModel):
    """句子练习"""

    file_name: str = None


class TransformSpeechDTO(BaseModel):
    """消息转语音"""

    message_id: constr(min_length=5)


class VoiceTranslateDTO(BaseModel):
    """语音转文字"""

    file_name: constr(min_length=1)


class TranslateDTO(BaseModel):
    """翻译"""

    message_id: constr(min_length=1)


class TranslateTextDTO(BaseModel):
    """翻译"""

    text: constr(min_length=1)
    session_id: str = None


class GrammarDTO(BaseModel):
    """分析英文的语法错误"""

    message_id: constr(min_length=1)


class WordDetailDTO(BaseModel):
    """单词详情"""

    word: constr(min_length=1)


class WordPracticeDTO(BaseModel):
    """单词练习"""

    session_id: str = None
    word: constr(min_length=1)
    file_name: constr(min_length=1)


class CollectDTO(BaseModel):
    """收藏单词或者句子"""

    type: constr(min_length=1)
    message_id: str = None
    content: str = None


class PromptDTO(BaseModel):
    """帮助用户生成提示句"""

    session_id: constr(min_length=1)


class CreateSessionDTO(BaseModel):
    role_name: str


class UpdateRoleDTO(BaseModel):
    language: str
    role_name: str
    style: str = None
    avatar: str
    local_name: str


class UpdateLanguageDTO(BaseModel):
    language: constr(min_length=1)


class AccountSettingsDTO(BaseModel):
    target_language: str | None = None
    speech_role_name: str | None = None
    auto_playing_voice: int = 1
    playing_voice_speed: str = "1.0"
    auto_text_shadow: int = 1
    auto_pronunciation: int = 1
