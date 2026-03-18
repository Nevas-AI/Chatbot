"""
dashboard_routes.py - Dashboard API Endpoints (Multi-Client)
=============================================================
REST + WebSocket endpoints for the Aria Dashboard.
Provides client management, conversation management, escalation controls,
analytics stats, user management, and real-time live updates.

All tenant-scoped queries accept an optional client_id query parameter.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select, func, and_, or_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field

from database import get_db
from models import Client, Conversation, Message, EscalationEvent, DashboardSettings, ChatUser, Lead
from lead_capture import encrypt_password, decrypt_password, send_test_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

# ─────────────────────────────────────────────
# Active WebSocket connections (for live updates)
# ─────────────────────────────────────────────
active_connections: List[WebSocket] = []


async def broadcast(event: dict):
    """Send a JSON event to all connected dashboard clients."""
    data = json.dumps(event, default=str)
    disconnected = []
    for ws in active_connections:
        try:
            await ws.send_text(data)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        active_connections.remove(ws)


# ─────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────
class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    message_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    id: str
    session_id: str
    user_ip: Optional[str] = None
    page_url: Optional[str] = None
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    message_count: int

    class Config:
        from_attributes = True


class ConversationDetailOut(ConversationOut):
    messages: List[MessageOut] = []


class EscalationOut(BaseModel):
    id: str
    conversation_id: str
    trigger_keyword: str
    status: str
    assigned_agent: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class StatsOut(BaseModel):
    total_conversations: int
    active_conversations: int
    escalations_today: int
    avg_messages_per_conversation: float
    conversations_today: int
    total_users: int


class SettingsOut(BaseModel):
    key: str
    value: dict
    updated_at: datetime

    class Config:
        from_attributes = True


class SettingsUpdateIn(BaseModel):
    key: str
    value: dict


class ChatUserOut(BaseModel):
    id: str
    identifier: str
    ip_address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    device_type: Optional[str] = None
    first_seen: datetime
    last_seen: datetime
    last_page: Optional[str] = None
    total_conversations: int
    total_messages: int
    tags: Optional[dict] = None

    class Config:
        from_attributes = True


class ChatUserDetailOut(ChatUserOut):
    conversations: List[ConversationOut] = []


class TagsUpdateIn(BaseModel):
    tags: dict


# ── Client schemas ──

class ClientOut(BaseModel):
    id: str
    name: str
    slug: str
    bot_name: str
    primary_color: str
    welcome_msg: Optional[str] = None
    logo_url: Optional[str] = None
    company_name: str
    support_email: str
    support_phone: str
    business_hours: str
    website_url: Optional[str] = None
    collection_name: str
    escalation_keywords: Optional[dict] = None
    lead_email: Optional[str] = None
    email_enabled: bool = False
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ClientCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    bot_name: str = Field("Neva", max_length=100)
    primary_color: str = Field("#6366F1", max_length=20)
    welcome_msg: Optional[str] = None
    logo_url: Optional[str] = None
    company_name: str = Field("Your Company", max_length=200)
    support_email: str = Field("support@yourcompany.com", max_length=200)
    support_phone: str = Field("+91-XXXXXXXXXX", max_length=50)
    business_hours: str = Field("Mon-Fri 9AM-6PM IST", max_length=100)
    website_url: Optional[str] = None
    collection_name: Optional[str] = None
    escalation_keywords: Optional[dict] = None
    lead_email: Optional[str] = None
    lead_email_password: Optional[str] = None
    email_enabled: bool = False


class ClientUpdateIn(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    bot_name: Optional[str] = Field(None, max_length=100)
    primary_color: Optional[str] = Field(None, max_length=20)
    welcome_msg: Optional[str] = None
    logo_url: Optional[str] = None
    company_name: Optional[str] = Field(None, max_length=200)
    support_email: Optional[str] = Field(None, max_length=200)
    support_phone: Optional[str] = Field(None, max_length=50)
    business_hours: Optional[str] = Field(None, max_length=100)
    website_url: Optional[str] = None
    collection_name: Optional[str] = None
    escalation_keywords: Optional[dict] = None
    is_active: Optional[bool] = None
    lead_email: Optional[str] = None
    lead_email_password: Optional[str] = None
    email_enabled: Optional[bool] = None


# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────

class LoginRequest(BaseModel):
    password: str


@router.post("/login")
async def dashboard_login(req: LoginRequest):
    expected_password = os.getenv("DASHBOARD_PASSWORD", "nevaadmin")
    if req.password == expected_password:
        return {"token": "valid_token"}
    raise HTTPException(status_code=401, detail="Invalid internal access code")


# ─────────────────────────────────────────────
# Client CRUD
# ─────────────────────────────────────────────

def _client_to_out(c: Client) -> ClientOut:
    """Helper to convert a Client ORM object to ClientOut schema."""
    return ClientOut(
        id=str(c.id),
        name=c.name,
        slug=c.slug,
        bot_name=c.bot_name,
        primary_color=c.primary_color,
        welcome_msg=c.welcome_msg,
        logo_url=c.logo_url,
        company_name=c.company_name,
        support_email=c.support_email,
        support_phone=c.support_phone,
        business_hours=c.business_hours,
        website_url=c.website_url,
        collection_name=c.collection_name,
        escalation_keywords=c.escalation_keywords,
        lead_email=c.lead_email,
        email_enabled=c.email_enabled,
        is_active=c.is_active,
        created_at=c.created_at,
    )

@router.get("/clients", response_model=List[ClientOut])
async def list_clients(
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """List all clients."""
    query = select(Client).order_by(Client.created_at)
    if not include_inactive:
        query = query.where(Client.is_active == True)

    result = await db.execute(query)
    clients = result.scalars().all()

    return [_client_to_out(c) for c in clients]


@router.post("/clients", response_model=ClientOut, status_code=201)
async def create_client(
    body: ClientCreateIn,
    db: AsyncSession = Depends(get_db),
):
    """Create a new client."""
    # Check slug uniqueness
    existing = await db.execute(
        select(Client).where(Client.slug == body.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Slug '{body.slug}' already exists")

    # Encrypt email password if provided
    encrypted_pwd = None
    if body.lead_email_password:
        encrypted_pwd = encrypt_password(body.lead_email_password)

    client = Client(
        name=body.name,
        slug=body.slug,
        bot_name=body.bot_name,
        primary_color=body.primary_color,
        welcome_msg=body.welcome_msg,
        logo_url=body.logo_url,
        company_name=body.company_name,
        support_email=body.support_email,
        support_phone=body.support_phone,
        business_hours=body.business_hours,
        website_url=body.website_url,
        collection_name=body.collection_name or body.slug,
        escalation_keywords=body.escalation_keywords,
        lead_email=body.lead_email,
        lead_email_password=encrypted_pwd,
        email_enabled=body.email_enabled,
    )
    db.add(client)
    await db.flush()
    await db.refresh(client)

    # Initialize pipeline for new client (import here to avoid circular)
    try:
        from main import init_client_pipeline, client_pipelines, client_escalation_handlers, client_configs, _build_client_config
        config = _build_client_config(client)
        client_configs[str(client.id)] = config
        pipeline, handler = init_client_pipeline(config)
        client_pipelines[str(client.id)] = pipeline
        client_escalation_handlers[str(client.id)] = handler
        logger.info(f"Initialized pipeline for new client '{client.name}'")
    except Exception as e:
        logger.warning(f"Could not auto-init pipeline for new client: {e}")

    return _client_to_out(client)


@router.get("/clients/{client_id}", response_model=ClientOut)
async def get_client(client_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single client's details."""
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return _client_to_out(client)


@router.put("/clients/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: UUID,
    body: ClientUpdateIn,
    db: AsyncSession = Depends(get_db),
):
    """Update a client's settings."""
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Apply updates — encrypt password if provided
    update_data = body.model_dump(exclude_unset=True)
    if "lead_email_password" in update_data and update_data["lead_email_password"]:
        update_data["lead_email_password"] = encrypt_password(update_data["lead_email_password"])
    elif "lead_email_password" in update_data and not update_data["lead_email_password"]:
        # If empty string, keep existing password
        del update_data["lead_email_password"]
    for field, value in update_data.items():
        setattr(client, field, value)

    await db.flush()
    await db.refresh(client)

    # Reinitialize pipeline with updated config
    try:
        from main import init_client_pipeline, client_pipelines, client_escalation_handlers, client_configs, _build_client_config
        config = _build_client_config(client)
        client_configs[str(client.id)] = config
        pipeline, handler = init_client_pipeline(config)
        client_pipelines[str(client.id)] = pipeline
        client_escalation_handlers[str(client.id)] = handler
        logger.info(f"Reinitialized pipeline for client '{client.name}'")
    except Exception as e:
        logger.warning(f"Could not reinit pipeline for client: {e}")

    return _client_to_out(client)


@router.delete("/clients/{client_id}")
async def delete_client(client_id: UUID, db: AsyncSession = Depends(get_db)):
    """Soft-delete a client (set is_active=False)."""
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client.is_active = False
    await db.flush()

    # Remove from pipeline cache
    try:
        from main import client_pipelines, client_escalation_handlers, client_configs
        cid = str(client.id)
        client_pipelines.pop(cid, None)
        client_escalation_handlers.pop(cid, None)
        client_configs.pop(cid, None)
    except Exception:
        pass

    return {"status": "deleted", "client_id": str(client_id)}


# ─────────────────────────────────────────────
# Conversations (scoped by client_id)
# ─────────────────────────────────────────────

@router.get("/conversations", response_model=List[ConversationOut])
async def list_conversations(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in messages"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List conversations with pagination, filters, search, and client scoping."""
    query = select(Conversation).order_by(desc(Conversation.started_at))

    conditions = []
    if client_id:
        try:
            conditions.append(Conversation.client_id == UUID(client_id))
        except ValueError:
            pass
    if status:
        conditions.append(Conversation.status == status)
    if date_from:
        conditions.append(Conversation.started_at >= date_from)
    if date_to:
        conditions.append(Conversation.started_at <= date_to)
    if conditions:
        query = query.where(and_(*conditions))

    if search:
        subq = (
            select(Message.conversation_id)
            .where(Message.content.ilike(f"%{search}%"))
            .distinct()
            .subquery()
        )
        query = query.where(Conversation.id.in_(select(subq.c.conversation_id)))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    conversations = result.scalars().all()

    return [
        ConversationOut(
            id=str(c.id),
            session_id=c.session_id,
            user_ip=c.user_ip,
            page_url=c.page_url,
            status=c.status,
            started_at=c.started_at,
            ended_at=c.ended_at,
            message_count=c.message_count,
        )
        for c in conversations
    ]


@router.get("/conversations/active", response_model=List[ConversationOut])
async def get_active_conversations(
    client_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get all currently active (live) conversations."""
    query = (
        select(Conversation)
        .where(Conversation.status == "active")
        .order_by(desc(Conversation.started_at))
    )
    if client_id:
        try:
            query = query.where(Conversation.client_id == UUID(client_id))
        except ValueError:
            pass

    result = await db.execute(query)
    conversations = result.scalars().all()

    return [
        ConversationOut(
            id=str(c.id),
            session_id=c.session_id,
            user_ip=c.user_ip,
            page_url=c.page_url,
            status=c.status,
            started_at=c.started_at,
            ended_at=c.ended_at,
            message_count=c.message_count,
        )
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(conversation_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single conversation with all its messages."""
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetailOut(
        id=str(conversation.id),
        session_id=conversation.session_id,
        user_ip=conversation.user_ip,
        page_url=conversation.page_url,
        status=conversation.status,
        started_at=conversation.started_at,
        ended_at=conversation.ended_at,
        message_count=conversation.message_count,
        messages=[
            MessageOut(
                id=str(m.id),
                role=m.role,
                content=m.content,
                message_type=m.message_type,
                created_at=m.created_at,
            )
            for m in conversation.messages
        ],
    )


# ─────────────────────────────────────────────
# Stats (scoped by client_id)
# ─────────────────────────────────────────────

@router.get("/stats", response_model=StatsOut)
async def get_stats(
    client_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard overview statistics, optionally scoped by client."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Build client filter
    conv_client_filter = []
    esc_client_filter = []
    user_client_filter = []
    if client_id:
        try:
            cid = UUID(client_id)
            conv_client_filter = [Conversation.client_id == cid]
            esc_client_filter = [EscalationEvent.client_id == cid]
            user_client_filter = [ChatUser.client_id == cid]
        except ValueError:
            pass

    # Total conversations
    total = await db.execute(
        select(func.count(Conversation.id)).where(*conv_client_filter) if conv_client_filter
        else select(func.count(Conversation.id))
    )
    total_count = total.scalar() or 0

    # Active conversations
    active_filters = [Conversation.status == "active"] + conv_client_filter
    active = await db.execute(
        select(func.count(Conversation.id)).where(and_(*active_filters))
    )
    active_count = active.scalar() or 0

    # Escalations today
    esc_filters = [EscalationEvent.created_at >= today_start] + esc_client_filter
    esc_today = await db.execute(
        select(func.count(EscalationEvent.id)).where(and_(*esc_filters))
    )
    esc_today_count = esc_today.scalar() or 0

    # Average messages per conversation
    if conv_client_filter:
        avg_msgs = await db.execute(
            select(func.avg(Conversation.message_count)).where(*conv_client_filter)
        )
    else:
        avg_msgs = await db.execute(select(func.avg(Conversation.message_count)))
    avg_msg_count = avg_msgs.scalar() or 0.0

    # Conversations today
    today_filters = [Conversation.started_at >= today_start] + conv_client_filter
    convos_today = await db.execute(
        select(func.count(Conversation.id)).where(and_(*today_filters))
    )
    convos_today_count = convos_today.scalar() or 0

    # Total users
    if user_client_filter:
        total_users_q = await db.execute(
            select(func.count(ChatUser.id)).where(*user_client_filter)
        )
    else:
        total_users_q = await db.execute(select(func.count(ChatUser.id)))
    total_users_count = total_users_q.scalar() or 0

    return StatsOut(
        total_conversations=total_count,
        active_conversations=active_count,
        escalations_today=esc_today_count,
        avg_messages_per_conversation=round(float(avg_msg_count), 1),
        conversations_today=convos_today_count,
        total_users=total_users_count,
    )


# ─────────────────────────────────────────────
# Escalations (scoped by client_id)
# ─────────────────────────────────────────────

@router.get("/escalations", response_model=List[EscalationOut])
async def list_escalations(
    client_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List escalation events with optional status and client filter."""
    query = select(EscalationEvent).order_by(desc(EscalationEvent.created_at))

    conditions = []
    if client_id:
        try:
            conditions.append(EscalationEvent.client_id == UUID(client_id))
        except ValueError:
            pass
    if status:
        conditions.append(EscalationEvent.status == status)
    if conditions:
        query = query.where(and_(*conditions))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    events = result.scalars().all()

    return [
        EscalationOut(
            id=str(e.id),
            conversation_id=str(e.conversation_id),
            trigger_keyword=e.trigger_keyword,
            status=e.status,
            assigned_agent=e.assigned_agent,
            resolved_at=e.resolved_at,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.post("/escalations/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Mark an escalation as resolved."""
    result = await db.execute(
        select(EscalationEvent).where(EscalationEvent.id == escalation_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Escalation not found")

    event.status = "resolved"
    event.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    await broadcast({
        "type": "escalation_updated",
        "escalation_id": str(event.id),
        "status": "resolved",
    })

    return {"status": "resolved"}


# ─────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────

@router.get("/settings", response_model=List[SettingsOut])
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Get all dashboard settings."""
    result = await db.execute(select(DashboardSettings))
    settings = result.scalars().all()
    return [
        SettingsOut(key=s.key, value=s.value, updated_at=s.updated_at)
        for s in settings
    ]


@router.put("/settings")
async def update_settings(
    body: SettingsUpdateIn,
    db: AsyncSession = Depends(get_db),
):
    """Create or update a dashboard setting."""
    result = await db.execute(
        select(DashboardSettings).where(DashboardSettings.key == body.key)
    )
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = body.value
    else:
        setting = DashboardSettings(key=body.key, value=body.value)
        db.add(setting)

    await db.flush()
    return {"status": "updated", "key": body.key}


# ─────────────────────────────────────────────
# WebSocket — Live dashboard updates
# ─────────────────────────────────────────────

@router.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    await ws.accept()
    active_connections.append(ws)
    logger.info(f"Dashboard WebSocket connected. Total: {len(active_connections)}")

    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        active_connections.remove(ws)
        logger.info(f"Dashboard WebSocket disconnected. Total: {len(active_connections)}")
    except Exception:
        if ws in active_connections:
            active_connections.remove(ws)


# ─────────────────────────────────────────────
# Users (scoped by client_id)
# ─────────────────────────────────────────────

@router.get("/users", response_model=List[ChatUserOut])
async def list_users(
    client_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search by IP or browser"),
    device_type: Optional[str] = Query(None),
    sort_by: str = Query("last_seen", description="Sort field"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List chatbot users with pagination, search, sorting, and client scoping."""
    query = select(ChatUser)

    conditions = []
    if client_id:
        try:
            conditions.append(ChatUser.client_id == UUID(client_id))
        except ValueError:
            pass

    if search:
        conditions.append(
            or_(
                ChatUser.ip_address.ilike(f"%{search}%"),
                ChatUser.browser.ilike(f"%{search}%"),
                ChatUser.city.ilike(f"%{search}%"),
                ChatUser.country.ilike(f"%{search}%"),
            )
        )
    if device_type:
        conditions.append(ChatUser.device_type == device_type)

    if conditions:
        query = query.where(and_(*conditions))

    sort_col = getattr(ChatUser, sort_by, ChatUser.last_seen)
    query = query.order_by(desc(sort_col))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    users = result.scalars().all()

    return [
        ChatUserOut(
            id=str(u.id),
            identifier=u.identifier,
            ip_address=u.ip_address,
            city=u.city,
            country=u.country,
            browser=u.browser,
            os=u.os,
            device_type=u.device_type,
            first_seen=u.first_seen,
            last_seen=u.last_seen,
            last_page=u.last_page,
            total_conversations=u.total_conversations,
            total_messages=u.total_messages,
            tags=u.tags,
        )
        for u in users
    ]


@router.get("/users/{user_id}", response_model=ChatUserDetailOut)
async def get_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a user's details with their conversation history."""
    result = await db.execute(
        select(ChatUser)
        .options(selectinload(ChatUser.conversations))
        .where(ChatUser.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return ChatUserDetailOut(
        id=str(user.id),
        identifier=user.identifier,
        ip_address=user.ip_address,
        city=user.city,
        country=user.country,
        browser=user.browser,
        os=user.os,
        device_type=user.device_type,
        first_seen=user.first_seen,
        last_seen=user.last_seen,
        last_page=user.last_page,
        total_conversations=user.total_conversations,
        total_messages=user.total_messages,
        tags=user.tags,
        conversations=[
            ConversationOut(
                id=str(c.id),
                session_id=c.session_id,
                user_ip=c.user_ip,
                page_url=c.page_url,
                status=c.status,
                started_at=c.started_at,
                ended_at=c.ended_at,
                message_count=c.message_count,
            )
            for c in sorted(user.conversations, key=lambda x: x.started_at, reverse=True)
        ],
    )


@router.put("/users/{user_id}/tags")
async def update_user_tags(
    user_id: UUID,
    body: TagsUpdateIn,
    db: AsyncSession = Depends(get_db),
):
    """Update a user's tags/notes."""
    result = await db.execute(
        select(ChatUser).where(ChatUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.tags = body.tags
    await db.flush()
    return {"status": "updated", "tags": body.tags}


# ─────────────────────────────────────────────
# Leads
# ─────────────────────────────────────────────

class LeadOut(BaseModel):
    id: str
    client_id: str
    conversation_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    email_sent: bool
    email_error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/leads", response_model=List[LeadOut])
async def list_leads(
    client_id: Optional[str] = Query(None),
    email_sent: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List captured leads with optional filters."""
    query = select(Lead).order_by(desc(Lead.created_at))

    conditions = []
    if client_id:
        try:
            conditions.append(Lead.client_id == UUID(client_id))
        except ValueError:
            pass
    if email_sent is not None:
        conditions.append(Lead.email_sent == email_sent)
    if conditions:
        query = query.where(and_(*conditions))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    leads = result.scalars().all()

    return [
        LeadOut(
            id=str(l.id),
            client_id=str(l.client_id),
            conversation_id=str(l.conversation_id) if l.conversation_id else None,
            name=l.name,
            email=l.email,
            phone=l.phone,
            company=l.company,
            email_sent=l.email_sent,
            email_error=l.email_error,
            created_at=l.created_at,
        )
        for l in leads
    ]


@router.post("/clients/{client_id}/test-email")
async def test_client_email(client_id: UUID, db: AsyncSession = Depends(get_db)):
    """Send a test email to verify a client's Gmail SMTP configuration."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not client.lead_email or not client.lead_email_password:
        raise HTTPException(
            status_code=400,
            detail="Email address and app password must be configured first."
        )

    try:
        decrypted_pwd = decrypt_password(client.lead_email_password)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Failed to decrypt stored password. Please re-enter your app password."
        )

    success, error = send_test_email(
        sender_email=client.lead_email,
        sender_password=decrypted_pwd,
        company_name=client.company_name,
    )

    if success:
        return {"status": "success", "message": "Test email sent successfully!"}
    else:
        raise HTTPException(status_code=400, detail=error or "Failed to send test email")

