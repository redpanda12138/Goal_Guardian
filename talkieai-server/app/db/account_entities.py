import datetime
from sqlalchemy import Column, String, DateTime, Integer, Index
from app.db import Base

class AccountEntity(Base):
    """用户账户表"""
    
    __tablename__ = "account"

    id = Column(String(80), primary_key=True)
    fingerprint = Column(String(64), nullable=True)  # 访客登录用
    username = Column(String(80), nullable=True, unique=True)  # 用户名登录用
    password = Column(String(255), nullable=True)  # 密码哈希值
    client_host = Column(String(50), nullable=True)
    user_agent = Column(String(512), nullable=True)
    status = Column(String(50), default="ACTIVE")
    create_time = Column("create_time", DateTime, default=datetime.datetime.now)
    update_time = Column("update_time", DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    # 添加索引以提高查询性能
    fingerprint_index = Index("idx_account_fingerprint", fingerprint)
    username_index = Index("idx_account_username", username)
    status_index = Index("idx_account_status", status)

class AccountSettingsEntity(Base):
    """用户设置表"""

    __tablename__ = "account_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(80), nullable=False)
    source_language = Column(String(80), nullable=False)
    target_language = Column(String(80), nullable=False)
    speech_role_name = Column(String(80), nullable=True)
    auto_playing_voice = Column(Integer, default=1)
    playing_voice_speed = Column(String(50), default='1.0')
    auto_text_shadow = Column(Integer, default=1)
    auto_pronunciation = Column(Integer, default=1)
    create_time = Column(DateTime, default=datetime.datetime.now)
    update_time = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    
    # 添加索引
    account_id_index = Index("idx_account_settings_account_id", account_id)

class AccountCollectEntity(Base):
    """用户收藏表"""

    __tablename__ = "account_collect"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(80), nullable=True)
    account_id = Column(String(80), nullable=False)
    type = Column(String(80), nullable=False)
    content = Column(String(2500), nullable=True)
    translation = Column(String(2500), nullable=True)
    deleted = Column(Integer, default=0)
    create_time = Column(DateTime, default=datetime.datetime.now)
    update_time = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    
    # 添加索引
    account_id_index = Index("idx_account_collect_account_id", account_id)
    message_id_index = Index("idx_account_collect_message_id", message_id)
    type_index = Index("idx_account_collect_type", type)
    deleted_index = Index("idx_account_collect_deleted", deleted)

# 数据库未创建表的话自动创建表
from app.db import engine
Base.metadata.create_all(engine)