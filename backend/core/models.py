from datetime import datetime, timezone

from core.dependencies import Base
from sqlalchemy import Column, Integer, String, Boolean, JSON
from sqlalchemy import Text, DateTime, ForeignKey


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


class AgentConversation(Base):
    __tablename__ = 'agent_conversations'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    title = Column(String(200))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc))


class AgentMessage(Base):
    __tablename__ = 'agent_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey('agent_conversations.id'), nullable=False, index=True)
    role = Column(String(32), nullable=False)  # 'user' | 'assistant' | 'system'
    content = Column(Text, nullable=False)
    meta = Column(JSON)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
