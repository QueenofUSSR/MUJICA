from datetime import datetime, timezone

from core.dependencies import Base
from sqlalchemy import Column, Integer, String, Boolean, JSON
from sqlalchemy import Text, DateTime, ForeignKey, Float


# 用户表
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)
    phone = Column(String(20))
    email = Column(String(50))
    avatar = Column(String(60))
    is_active = Column(Boolean, default=True, nullable=False)  # 账号启用/禁用


class AgentSession(Base):
    __tablename__ = 'agent_sessions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    model_id = Column(String(80), nullable=True)
    status = Column(String(40), default='pending', nullable=False)
    metadata_ = Column('metadata', JSON)
    # Aggregated final result and auto-generated short title
    final_result = Column(JSON)
    summary_title = Column(String(200))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc))


class AgentRole(Base):
    __tablename__ = 'agent_roles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(80), unique=True, nullable=False)
    description = Column(Text)
    capabilities = Column(JSON)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc))


class AgentTask(Base):
    __tablename__ = 'agent_tasks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('agent_sessions.id'), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey('agent_tasks.id'), nullable=True, index=True)
    assigned_role_id = Column(Integer, ForeignKey('agent_roles.id'), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(40), default='pending', nullable=False)
    confidence = Column(Float, nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    result = Column(JSON)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc))


class AgentTaskLog(Base):
    __tablename__ = 'agent_task_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('agent_sessions.id'), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey('agent_tasks.id'), nullable=True, index=True)
    role_id = Column(Integer, ForeignKey('agent_roles.id'), nullable=True, index=True)
    level = Column(String(32), default='INFO', nullable=False)
    message = Column(Text, nullable=False)
    payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
