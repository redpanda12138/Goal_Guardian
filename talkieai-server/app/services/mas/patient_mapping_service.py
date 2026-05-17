"""
患者映射服务：管理account_id到patient_id的映射关系
"""
from sqlalchemy.orm import Session
from app.db.mas_entities import PatientMappingEntity
from app.core.utils import short_uuid
from app.core.logging import logging


class PatientMappingService:
    """患者映射服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_patient_id(self, account_id: str) -> str:
        """
        获取或创建patient_id（使用账户ID的哈希值确保一致性）
        """
        import hashlib
        
        mapping = self.db.query(PatientMappingEntity).filter_by(
            account_id=account_id
        ).first()
        
        if mapping:
            return mapping.patient_id
        
        # 使用account_id的哈希值生成一致的patient_id
        hash_value = hashlib.md5(account_id.encode()).hexdigest()[:8]
        patient_id = f"patient_{hash_value}"
        
        # 检查是否已存在该patient_id（防止冲突）
        existing = self.db.query(PatientMappingEntity).filter_by(
            patient_id=patient_id
        ).first()
        
        if existing:
            # 如果存在冲突，使用UUID
            patient_id = f"patient_{short_uuid()}"
        
        mapping = PatientMappingEntity(
            id=f"mapping_{short_uuid()}",
            account_id=account_id,
            patient_id=patient_id
        )
        self.db.add(mapping)
        self.db.commit()
        return patient_id
    
    def get_account_id(self, patient_id: str) -> str:
        """
        根据patient_id获取account_id
        
        Args:
            patient_id: 患者ID
            
        Returns:
            account_id: 账户ID，如果不存在返回None
        """
        mapping = self.db.query(PatientMappingEntity).filter_by(
            patient_id=patient_id
        ).first()
        return mapping.account_id if mapping else None
    
    def get_patient_id(self, account_id: str) -> str:
        """
        根据account_id获取patient_id（如果不存在返回None）
        
        Args:
            account_id: 账户ID
            
        Returns:
            patient_id: 患者ID，如果不存在返回None
        """
        mapping = self.db.query(PatientMappingEntity).filter_by(
            account_id=account_id
        ).first()
        return mapping.patient_id if mapping else None
