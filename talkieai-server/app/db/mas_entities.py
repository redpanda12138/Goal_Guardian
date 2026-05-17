'''
MAS系统相关的数据库实体
'''
import datetime
from sqlalchemy import Column, String, DateTime, Index
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


# 创建表（如果不存在）
Base.metadata.create_all(engine)
