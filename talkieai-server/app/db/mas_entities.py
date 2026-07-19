'''
MAS系统相关的数据库实体
'''
import datetime
from sqlalchemy import Column, String, DateTime, Index, Integer, Text
from app.db import Base, engine


class PatientMappingEntity(Base):
    """账户到患者的映射表"""
    
    __tablename__ = "patient_mapping"
    
    id = Column("id", String(80), primary_key=True)
    account_id = Column("account_id", String(80), unique=True, nullable=False)
    patient_id = Column("patient_id", String(80), unique=True, nullable=False)
    created_at = Column("created_at", DateTime, default=datetime.datetime.now)
    updated_at = Column("updated_at", DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    
    # 添加索引以提高查询性能
    account_id_index = Index("idx_patient_mapping_account_id", account_id)
    patient_id_index = Index("idx_patient_mapping_patient_id", patient_id)


class WorkflowToolConfirmationEntity(Base):
    """Persisted user decision boundary for one model-proposed write tool."""

    __tablename__ = "workflow_tool_confirmation"

    action_id = Column("action_id", String(80), primary_key=True)
    account_id = Column("account_id", String(80), nullable=False)
    session_id = Column("session_id", String(80), nullable=False)
    message_id = Column("message_id", String(80), unique=True, nullable=False)
    turn_index = Column("turn_index", Integer, nullable=False)
    tool_request_json = Column("tool_request_json", Text, nullable=False)
    status = Column("status", String(20), nullable=False, default="pending")
    created_at = Column("created_at", DateTime, default=datetime.datetime.now)
    updated_at = Column(
        "updated_at",
        DateTime,
        default=datetime.datetime.now,
        onupdate=datetime.datetime.now,
    )

    account_index = Index("idx_workflow_tool_confirmation_account", account_id)
    session_index = Index("idx_workflow_tool_confirmation_session", session_id)


# 创建表（如果不存在）
Base.metadata.create_all(engine)
