"""
models.py - SQLAlchemy ORM Models for Aria Dashboard
=====================================================
Defines Client, ChatUser, Conversation, Message, EscalationEvent,
and DashboardSettings tables. All tenant-scoped tables carry a client_id FK.
"""

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from database import Base


# ─────────────────────────────────────────────
# Client (tenant)
# ─────────────────────────────────────────────
class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    # Branding
    bot_name: Mapped[str] = mapped_column(String(100), default="Neva")
    primary_color: Mapped[str] = mapped_column(String(20), default="#6366F1")
    welcome_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Business config
    company_name: Mapped[str] = mapped_column(String(200), default="Your Company")
    support_email: Mapped[str] = mapped_column(String(200), default="support@yourcompany.com")
    support_phone: Mapped[str] = mapped_column(String(50), default="+91-XXXXXXXXXX")
    business_hours: Mapped[str] = mapped_column(String(100), default="Mon-Fri 9AM-6PM IST")
    website_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # RAG config
    collection_name: Mapped[str] = mapped_column(String(200), default="default_knowledge")

    # Escalation keywords override (JSON array, nullable => use defaults)
    escalation_keywords: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Email / Lead notification config (Gmail only, per-client)
    lead_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    lead_email_password: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # Fernet-encrypted Gmail App Password
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Microsoft Bookings integration
    booking_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # Meta
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    chat_users: Mapped[List["ChatUser"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    escalation_events: Mapped[List["EscalationEvent"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    leads: Mapped[List["Lead"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    social_posts: Mapped[List["SocialPost"]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────
# ChatUser
# ─────────────────────────────────────────────
class ChatUser(Base):
    __tablename__ = "chat_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    identifier: Mapped[str] = mapped_column(
        String(128), index=True
    )  # fingerprint key (IP address)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    browser: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    os: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    device_type: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # desktop | mobile | tablet
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_page: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    total_conversations: Mapped[int] = mapped_column(Integer, default=0)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="chat_users")
    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_chat_users_last_seen", "last_seen"),
        Index("idx_chat_users_client_identifier", "client_id", "identifier", unique=True),
    )


# ─────────────────────────────────────────────
# Conversation
# ─────────────────────────────────────────────
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_users.id", ondelete="SET NULL"), nullable=True
    )
    user_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", index=True
    )  # active | ended | escalated
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="conversations")
    user: Mapped[Optional["ChatUser"]] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    escalation_events: Mapped[List["EscalationEvent"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_conversations_started_at", "started_at"),
        Index("idx_conversations_status_started", "status", "started_at"),
        Index("idx_conversations_user_id", "user_id"),
        Index("idx_conversations_client_status", "client_id", "status"),
    )


# ─────────────────────────────────────────────
# Message
# ─────────────────────────────────────────────
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(
        String(20)
    )  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(
        String(20), default="text"
    )  # text | escalation | error
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("idx_messages_conversation_created", "conversation_id", "created_at"),
    )


# ─────────────────────────────────────────────
# EscalationEvent
# ─────────────────────────────────────────────
class EscalationEvent(Base):
    __tablename__ = "escalation_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    trigger_keyword: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )  # pending | assigned | resolved
    assigned_agent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="escalation_events")
    conversation: Mapped["Conversation"] = relationship(
        back_populates="escalation_events"
    )

    __table_args__ = (
        Index("idx_escalations_status_created", "status", "created_at"),
        Index("idx_escalations_client_status", "client_id", "status"),
    )


# ─────────────────────────────────────────────
# DashboardSettings
# ─────────────────────────────────────────────
class DashboardSettings(Base):
    __tablename__ = "dashboard_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ─────────────────────────────────────────────
# Lead
# ─────────────────────────────────────────────
class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )

    # Captured lead fields
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Metadata
    raw_messages: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    email_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="leads")
    conversation: Mapped[Optional["Conversation"]] = relationship()

    __table_args__ = (
        Index("idx_leads_client_created", "client_id", "created_at"),
        Index("idx_leads_email_sent", "email_sent"),
    )


# ─────────────────────────────────────────────
# SocialPost
# ─────────────────────────────────────────────
class SocialPost(Base):
    __tablename__ = "social_posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), index=True
    )

    platform: Mapped[str] = mapped_column(
        String(50)
    )  # linkedin | facebook | instagram | twitter | other
    post_url: Mapped[str] = mapped_column(String(1000))
    content: Mapped[str] = mapped_column(Text)
    caption: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    ingested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="social_posts")

    __table_args__ = (
        Index("idx_social_posts_client_platform", "client_id", "platform"),
        Index("idx_social_posts_client_active", "client_id", "is_active"),
    )

