"""
main.py - FastAPI Application for Neva Chatbot (Multi-Client)
===============================================================
REST API backend with chat, ingestion, health check, and escalation endpoints.
Supports SSE streaming, CORS, session-based chat history, and background tasks.
Includes PostgreSQL persistence and WebSocket broadcasting for the dashboard.

Multi-client: each client has its own RAG pipeline, escalation handler,
and isolated data. Pipelines are lazily initialized and cached in memory.
"""

import os
import uuid
import json
import asyncio
import logging
import re as _re
import threading
from typing import Dict, List, Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from sqlalchemy import select

import schedule
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from scraper import WebScraper
from rag import RAGPipeline
from escalation import EscalationHandler

# Dashboard / DB imports
from database import init_db, async_session
from models import Client, Conversation, Message, EscalationEvent, ChatUser
from dashboard_routes import router as dashboard_router, broadcast

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Global state (shared across all clients)
# ─────────────────────────────────────────────
scraper: Optional[WebScraper] = None

# Per-client registries: keyed by client_id (UUID string)
client_pipelines: Dict[str, RAGPipeline] = {}
client_escalation_handlers: Dict[str, EscalationHandler] = {}
client_configs: Dict[str, dict] = {}  # cached config dicts

# In-memory session store: {session_id: [{"role": ..., "content": ...}, ...]}
chat_sessions: Dict[str, List[Dict]] = {}
# Map session → client_id for quick lookup
session_client_map: Dict[str, str] = {}

# Max messages to keep per session
MAX_HISTORY = 10


# ─────────────────────────────────────────────
# Client pipeline management
# ─────────────────────────────────────────────
def _build_client_config(client: Client) -> dict:
    """Build a config dict from a Client model instance."""
    return {
        "client_id": str(client.id),
        "slug": client.slug,
        "bot_name": client.bot_name,
        "company_name": client.company_name,
        "support_email": client.support_email,
        "support_phone": client.support_phone,
        "business_hours": client.business_hours,
        "website_url": client.website_url,
        "collection_name": client.collection_name or client.slug,
        "persist_dir": os.getenv("CHROMA_PERSIST_DIR", "./chroma_db"),
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "llm_model": os.getenv("LLM_MODEL", "llama3.1"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "nomic-embed-text"),
        "escalation_keywords": client.escalation_keywords,
        "primary_color": client.primary_color,
        "welcome_msg": client.welcome_msg,
        "logo_url": client.logo_url,
    }


def init_client_pipeline(config: dict) -> tuple:
    """Initialize a RAGPipeline and EscalationHandler from a config dict."""
    pipeline = RAGPipeline(config=config)
    handler = EscalationHandler(config=config)
    return pipeline, handler


async def load_all_client_pipelines():
    """Load all active clients from DB and initialize their pipelines."""
    global client_pipelines, client_escalation_handlers, client_configs
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Client).where(Client.is_active == True)
            )
            clients = result.scalars().all()

            for client in clients:
                cid = str(client.id)
                config = _build_client_config(client)
                client_configs[cid] = config
                try:
                    pipeline, handler = init_client_pipeline(config)
                    client_pipelines[cid] = pipeline
                    client_escalation_handlers[cid] = handler
                    logger.info(f"✅ Initialized pipeline for client '{client.name}' ({client.slug})")
                except Exception as e:
                    logger.error(f"❌ Failed to init pipeline for client '{client.name}': {e}")

            if not clients:
                logger.info("No clients found, will create default client on first request.")
    except Exception as e:
        logger.error(f"Failed to load client pipelines: {e}")


async def ensure_default_client() -> str:
    """Ensure a default client exists. Returns its ID as string."""
    async with async_session() as db:
        result = await db.execute(
            select(Client).where(Client.slug == "default")
        )
        client = result.scalar_one_or_none()

        if not client:
            client = Client(
                name=os.getenv("COMPANY_NAME", "Nevas Technologies"),
                slug="default",
                bot_name="Neva",
                primary_color="#6366F1",
                welcome_msg="Hi there! 👋 I'm Neva, your AI assistant. How can I help you today?",
                company_name=os.getenv("COMPANY_NAME", "Nevas Technologies"),
                support_email=os.getenv("SUPPORT_EMAIL", "info@nevastech.com"),
                support_phone=os.getenv("SUPPORT_PHONE", "+91 0123456789"),
                business_hours=os.getenv("BUSINESS_HOURS", "Mon-Sat 9AM-6PM IST"),
                website_url=os.getenv("WEBSITE_URL", ""),
                collection_name=os.getenv("CHROMA_COLLECTION_NAME", "aria_knowledge"),
            )
            db.add(client)
            await db.commit()
            await db.refresh(client)
            logger.info(f"✅ Created default client: {client.name}")

        cid = str(client.id)
        if cid not in client_pipelines:
            config = _build_client_config(client)
            client_configs[cid] = config
            pipeline, handler = init_client_pipeline(config)
            client_pipelines[cid] = pipeline
            client_escalation_handlers[cid] = handler

        return cid


async def get_client_id_by_slug(slug: str) -> Optional[str]:
    """Resolve a client slug to a client_id string."""
    # Check cache first
    for cid, cfg in client_configs.items():
        if cfg.get("slug") == slug:
            return cid

    # DB lookup
    async with async_session() as db:
        result = await db.execute(
            select(Client).where(Client.slug == slug, Client.is_active == True)
        )
        client = result.scalar_one_or_none()
        if client:
            cid = str(client.id)
            if cid not in client_pipelines:
                config = _build_client_config(client)
                client_configs[cid] = config
                pipeline, handler = init_client_pipeline(config)
                client_pipelines[cid] = pipeline
                client_escalation_handlers[cid] = handler
            return cid
    return None


def get_pipeline_for_client(client_id: str) -> RAGPipeline:
    """Get the RAG pipeline for a client, raising 404 if not found."""
    if client_id not in client_pipelines:
        raise HTTPException(status_code=404, detail=f"Client not found: {client_id}")
    return client_pipelines[client_id]


def get_escalation_for_client(client_id: str) -> EscalationHandler:
    """Get the escalation handler for a client."""
    if client_id not in client_escalation_handlers:
        raise HTTPException(status_code=404, detail=f"Client not found: {client_id}")
    return client_escalation_handlers[client_id]


# ─────────────────────────────────────────────
# Background scheduler for auto-refresh
# ─────────────────────────────────────────────
def _run_scheduler():
    """Background thread that runs the schedule loop."""
    while True:
        schedule.run_pending()
        import time
        time.sleep(60)


def _auto_refresh_task():
    """Scheduled task to re-scrape websites for all active clients."""
    global client_pipelines, client_configs
    for cid, config in client_configs.items():
        website_url = config.get("website_url", "")
        if not website_url:
            continue
        logger.info(f"AUTO_REFRESH: Re-scraping {website_url} for client {config.get('slug', cid)}")
        try:
            pipeline = client_pipelines.get(cid)
            if scraper and pipeline:
                documents = scraper.scrape_website(website_url)
                if documents:
                    pipeline.clear_collection()
                    pipeline.ingest_documents(documents)
                    # Re-ingest FAQs
                    faq_path = os.path.join(os.path.dirname(__file__), "faq.json")
                    if os.path.exists(faq_path):
                        pipeline.ingest_faqs(faq_path)
                    logger.info(f"AUTO_REFRESH: Updated {config.get('slug')} with {len(documents)} docs.")
        except Exception as e:
            logger.error(f"AUTO_REFRESH: Failed for {config.get('slug')}: {e}")


# ─────────────────────────────────────────────
# Application lifespan
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup and cleanup on shutdown."""
    global scraper

    logger.info("🚀 Starting Neva Chatbot Server (Multi-Client)...")

    # Initialize database tables
    try:
        await init_db()
        logger.info("✅ Database initialized.")
    except Exception as e:
        logger.error(f"❌ Database init failed: {str(e)}")
        raise

    # Initialize shared scraper
    max_pages = int(os.getenv("MAX_PAGES", "100"))
    scraper = WebScraper(max_pages=max_pages)

    # Ensure default client exists
    await ensure_default_client()

    # Load all client pipelines
    await load_all_client_pipelines()

    # Ingest FAQ data for all clients on startup
    faq_path = os.path.join(os.path.dirname(__file__), "faq.json")
    if os.path.exists(faq_path):
        for cid, pipeline in client_pipelines.items():
            try:
                if pipeline.vectorstore.count() == 0 or True:
                    count = pipeline.ingest_faqs(faq_path)
                    if count > 0:
                        logger.info(f"✅ Loaded {count} FAQ entries for client {client_configs.get(cid, {}).get('slug', cid)}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load FAQs for client {cid}: {str(e)}")

    # Setup auto-refresh schedule
    refresh_hours = int(os.getenv("AUTO_REFRESH_HOURS", "24"))
    schedule.every(refresh_hours).hours.do(_auto_refresh_task)
    scheduler_thread = threading.Thread(target=_run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info(f"⏰ Auto-refresh scheduled every {refresh_hours} hours.")

    yield  # Application runs here

    # Shutdown
    logger.info("🛑 Shutting down Neva Chatbot Server...")


# ─────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────
app = FastAPI(
    title="Neva Chatbot API (Multi-Client)",
    description="AI-powered ERP customer support chatbot with RAG capabilities — by Nevastech",
    version="2.0.0",
    lifespan=lifespan,
)

# Mount dashboard routes
app.include_router(dashboard_router)

# Enable CORS for all origins (widget can be embedded anywhere)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────
class ChatRequest(BaseModel):
    """Chat message request body."""
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    client_id: Optional[str] = Field(None, description="Client ID (UUID or slug)")
    page_url: Optional[str] = Field(None, description="URL of the page from which the user is chatting")


class ChatResponse(BaseModel):
    """Chat response body (non-streaming)."""
    response: str
    session_id: str
    is_escalation: bool = False
    escalation_data: Optional[Dict] = None


class IngestRequest(BaseModel):
    """Ingestion request body."""
    url: str = Field(..., description="Website URL to scrape and ingest")
    client_id: Optional[str] = Field(None, description="Client ID to ingest for")


class IngestResponse(BaseModel):
    """Ingestion response body."""
    status: str
    url: str
    documents_scraped: int
    chunks_created: int


class EscalateRequest(BaseModel):
    """Escalation request body."""
    message: Optional[str] = Field("User requested escalation", description="Reason for escalation")
    session_id: Optional[str] = None
    client_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response body."""
    status: str
    timestamp: str
    services: Dict


# ─────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────
def get_or_create_session(session_id: Optional[str] = None) -> str:
    """Get an existing session or create a new one."""
    if session_id and session_id in chat_sessions:
        return session_id
    new_id = session_id or str(uuid.uuid4())
    chat_sessions[new_id] = []
    return new_id


def add_to_history(session_id: str, role: str, content: str) -> None:
    """Add a message to the session's chat history, keeping last MAX_HISTORY messages."""
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
    chat_sessions[session_id].append({"role": role, "content": content})
    if len(chat_sessions[session_id]) > MAX_HISTORY:
        chat_sessions[session_id] = chat_sessions[session_id][-MAX_HISTORY:]


async def resolve_client_id(raw: Optional[str]) -> str:
    """Resolve a client_id from a raw string (UUID or slug). Falls back to default."""
    if not raw:
        return await ensure_default_client()

    # Check if it's already a known UUID
    if raw in client_pipelines:
        return raw

    # Try as slug
    cid = await get_client_id_by_slug(raw)
    if cid:
        return cid

    # Try as UUID string
    try:
        uuid.UUID(raw)
        if raw in client_pipelines:
            return raw
    except ValueError:
        pass

    # Fall back to default
    return await ensure_default_client()


def parse_user_agent(ua: Optional[str]) -> dict:
    """Extract browser, OS, and device type from a user-agent string."""
    if not ua:
        return {"browser": None, "os": None, "device_type": "desktop"}

    browser = None
    for name, pattern in [
        ("Edge", r"Edg[eA]?/(\S+)"),
        ("Chrome", r"Chrome/(\S+)"),
        ("Firefox", r"Firefox/(\S+)"),
        ("Safari", r"Version/(\S+).*Safari"),
        ("Opera", r"OPR/(\S+)"),
    ]:
        m = _re.search(pattern, ua)
        if m:
            browser = f"{name} {m.group(1).split('.')[0]}"
            break
    if not browser:
        browser = "Other"

    os_name = None
    if "Windows" in ua:
        os_name = "Windows"
    elif "Mac OS X" in ua or "Macintosh" in ua:
        os_name = "macOS"
    elif "Android" in ua:
        os_name = "Android"
    elif "iPhone" in ua or "iPad" in ua:
        os_name = "iOS"
    elif "Linux" in ua:
        os_name = "Linux"
    else:
        os_name = "Other"

    device_type = "desktop"
    if _re.search(r"Mobile|Android.*Mobile|iPhone", ua):
        device_type = "mobile"
    elif _re.search(r"iPad|Android(?!.*Mobile)|Tablet", ua):
        device_type = "tablet"

    return {"browser": browser, "os": os_name, "device_type": device_type}


def fetch_and_update_location(user_id: uuid.UUID, ip_address: str):
    """Fetch location from IP and update ChatUser record in a background thread."""
    if not ip_address or ip_address in ("127.0.0.1", "::1", "localhost"):
        return
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip_address}?fields=status,country,city", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                from database import SessionLocal
                from models import ChatUser as ChatUserModel
                with SessionLocal() as db:
                    user = db.query(ChatUserModel).filter(ChatUserModel.id == user_id).first()
                    if user:
                        if not user.city and data.get("city"):
                            user.city = data.get("city")
                        if not user.country and data.get("country"):
                            user.country = data.get("country")
                        db.commit()
    except Exception as e:
        logger.error(f"Failed to fetch GeoIP for {ip_address}: {e}")


async def persist_message(
    session_id: str,
    role: str,
    content: str,
    message_type: str = "text",
    user_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    page_url: Optional[str] = None,
    client_id: Optional[str] = None,
) -> None:
    """Persist a message to PostgreSQL, update ChatUser, and broadcast via WebSocket."""
    try:
        async with async_session() as db:
            # Resolve client_id
            resolved_client_id = None
            if client_id:
                try:
                    resolved_client_id = uuid.UUID(client_id)
                except ValueError:
                    pass

            # ── Get or create ChatUser ──
            chat_user = None
            if user_ip and role == "user" and resolved_client_id:
                identifier = user_ip
                result = await db.execute(
                    select(ChatUser).where(
                        ChatUser.identifier == identifier,
                        ChatUser.client_id == resolved_client_id,
                    )
                )
                chat_user = result.scalar_one_or_none()

                ua_info = parse_user_agent(user_agent)

                if not chat_user:
                    chat_user = ChatUser(
                        client_id=resolved_client_id,
                        identifier=identifier,
                        ip_address=user_ip,
                        browser=ua_info["browser"],
                        os=ua_info["os"],
                        device_type=ua_info["device_type"],
                        last_page=page_url,
                        total_conversations=0,
                        total_messages=0,
                    )
                    db.add(chat_user)
                    await db.flush()

                    if user_ip:
                        asyncio.create_task(asyncio.to_thread(fetch_and_update_location, chat_user.id, user_ip))
                else:
                    chat_user.last_seen = datetime.now(timezone.utc)
                    chat_user.browser = ua_info["browser"]
                    chat_user.os = ua_info["os"]
                    chat_user.device_type = ua_info["device_type"]
                    if page_url:
                        chat_user.last_page = page_url

                chat_user.total_messages += 1

            # ── Get or create conversation row ──
            result = await db.execute(
                select(Conversation).where(Conversation.session_id == session_id)
            )
            conversation = result.scalar_one_or_none()

            if not conversation:
                conversation = Conversation(
                    client_id=resolved_client_id,
                    session_id=session_id,
                    user_ip=user_ip,
                    user_agent=user_agent,
                    page_url=page_url,
                    user_id=chat_user.id if chat_user else None,
                    status="active",
                    message_count=0,
                )
                db.add(conversation)
                await db.flush()

                if chat_user:
                    chat_user.total_conversations += 1

            # Create message
            msg = Message(
                conversation_id=conversation.id,
                role=role,
                content=content,
                message_type=message_type,
            )
            db.add(msg)
            conversation.message_count += 1

            if message_type == "escalation":
                conversation.status = "escalated"

            await db.commit()

            await broadcast({
                "type": "new_message",
                "conversation_id": str(conversation.id),
                "session_id": session_id,
                "role": role,
                "content": content[:200],
                "message_type": message_type,
                "client_id": client_id,
            })
    except Exception as e:
        logger.error(f"Failed to persist message: {e}")


async def persist_escalation_event(
    session_id: str, trigger_keyword: str, client_id: Optional[str] = None
) -> None:
    """Create an EscalationEvent record in the database."""
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Conversation).where(Conversation.session_id == session_id)
            )
            conversation = result.scalar_one_or_none()
            if conversation:
                resolved_client_id = None
                if client_id:
                    try:
                        resolved_client_id = uuid.UUID(client_id)
                    except ValueError:
                        pass

                event = EscalationEvent(
                    client_id=resolved_client_id or conversation.client_id,
                    conversation_id=conversation.id,
                    trigger_keyword=trigger_keyword,
                    status="assigned",
                    assigned_agent="Admin",
                )
                db.add(event)
                conversation.status = "escalated"
                await db.commit()

                await broadcast({
                    "type": "new_escalation",
                    "conversation_id": str(conversation.id),
                    "session_id": session_id,
                    "trigger": trigger_keyword,
                    "status": "assigned",
                    "agent": "Admin",
                    "client_id": client_id,
                })
    except Exception as e:
        logger.error(f"Failed to persist escalation event: {e}")


async def close_conversation(session_id: str) -> None:
    """Mark a conversation as ended in the database."""
    try:
        async with async_session() as db:
            result = await db.execute(
                select(Conversation).where(Conversation.session_id == session_id)
            )
            conversation = result.scalar_one_or_none()
            if conversation:
                conversation.status = "ended"
                conversation.ended_at = datetime.now(timezone.utc)
                await db.commit()

                await broadcast({
                    "type": "conversation_ended",
                    "conversation_id": str(conversation.id),
                    "session_id": session_id,
                })
    except Exception as e:
        logger.error(f"Failed to close conversation: {e}")


# ─────────────────────────────────────────────
# Widget config endpoint (public, no auth)
# ─────────────────────────────────────────────
@app.get("/api/widget/config/{client_slug}", tags=["Widget"])
async def get_widget_config(client_slug: str):
    """Return public branding config for a client widget."""
    cid = await get_client_id_by_slug(client_slug)
    if not cid:
        # Fall back to default
        cid = await ensure_default_client()

    config = client_configs.get(cid, {})
    return {
        "client_id": cid,
        "bot_name": config.get("bot_name", "Neva"),
        "primary_color": config.get("primary_color", "#6366F1"),
        "company_name": config.get("company_name", "Your Company"),
        "welcome_msg": config.get("welcome_msg", "Hi there! 👋 How can I help you today?"),
        "logo_url": config.get("logo_url"),
    }


# ─────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint."""
    services = {
        "scraper": "up" if scraper else "down",
        "active_clients": len(client_pipelines),
    }

    try:
        import ollama as ollama_client
        models = ollama_client.list()
        available_models = [m.model for m in models.models] if models.models else []
        services["ollama"] = "up"
        services["available_models"] = available_models
    except Exception:
        services["ollama"] = "down"
        services["available_models"] = []

    for cid, pipeline in client_pipelines.items():
        slug = client_configs.get(cid, {}).get("slug", cid[:8])
        services[f"pipeline_{slug}"] = "up"
        services[f"knowledge_base_{slug}"] = pipeline.get_collection_stats().get("total_documents", 0)

    overall_status = "healthy" if services.get("ollama") == "up" and len(client_pipelines) > 0 else "degraded"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now().isoformat(),
        services=services,
    )


@app.post("/api/chat", tags=["Chat"])
async def chat(request: ChatRequest, req: Request):
    """
    Chat endpoint with Server-Sent Events (SSE) streaming.
    Routes to the correct client pipeline based on client_id.
    """
    # Resolve client
    client_id = await resolve_client_id(request.client_id)
    rag_pipeline = get_pipeline_for_client(client_id)
    escalation_handler = get_escalation_for_client(client_id)

    # Get or create session
    session_id = get_or_create_session(request.session_id)
    session_client_map[session_id] = client_id

    # Grab client info for DB
    user_ip = req.client.host if req.client else None
    user_agent = req.headers.get("user-agent")

    # Check if this session is already ended in the database
    async with async_session() as db:
        res = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
        conv = res.scalar_one_or_none()
        if conv and conv.status == "ended":
            async def closed_already_stream():
                data = json.dumps({
                    "type": "chat_closed",
                    "content": "This chat session has already been closed. Please start a new chat.",
                    "session_id": session_id,
                })
                yield f"data: {data}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(
                closed_already_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )

    # Direct escalation bypass via special command
    if request.message.strip() == "/connect_human_support_now":
        if escalation_handler.is_working_hours():
            add_to_history(session_id, "user", "I want to speak with human support")
            esc_msg = "I am connecting you with our human support team now. An agent will be with you shortly."
            add_to_history(session_id, "assistant", esc_msg)

            await persist_message(session_id, "user", "I want to speak with human support", "text", user_ip, user_agent, request.page_url, client_id)
            await persist_message(session_id, "assistant", esc_msg, "escalation", page_url=request.page_url, client_id=client_id)

            async with async_session() as db:
                res = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
                conv = res.scalar_one_or_none()
                if conv:
                    conv.status = "escalated"
                    await db.commit()
                    await broadcast({
                        "type": "conversation_escalated",
                        "conversation_id": str(conv.id),
                        "session_id": session_id,
                    })

            async def dir_esc_stream():
                data = json.dumps({"type": "token", "content": esc_msg, "session_id": session_id})
                yield f"data: {data}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                dir_esc_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
        else:
            add_to_history(session_id, "user", "I want to speak with human support")
            out_msg = (
                f"Our customer support is currently unavailable.\n\n"
                f"🕐 **Working Hours:** {escalation_handler.business_hours}\n"
                f"📧 **Email:** {escalation_handler.support_email}\n\n"
                f"Please leave your query and contact details here, and our team will get back to you soon."
            )
            add_to_history(session_id, "assistant", out_msg)
            await persist_message(session_id, "user", "I want to speak with human support", "text", user_ip, user_agent, request.page_url, client_id)
            await persist_message(session_id, "assistant", out_msg, "text", page_url=request.page_url, client_id=client_id)

            async def dir_out_stream():
                data = json.dumps({"type": "token", "content": out_msg, "session_id": session_id})
                yield f"data: {data}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(
                dir_out_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )

    # Check for escalation triggers
    escalation = escalation_handler.check_escalation(request.message)
    if escalation.should_escalate:
        add_to_history(session_id, "user", request.message)
        add_to_history(session_id, "assistant", escalation.message)

        await persist_message(session_id, "user", request.message, "text", user_ip, user_agent, request.page_url, client_id)
        await persist_message(session_id, "assistant", escalation.message, "escalation", page_url=request.page_url, client_id=client_id)
        await persist_escalation_event(session_id, escalation.trigger_keyword, client_id)

        async def escalation_stream():
            data = json.dumps({
                "type": "escalation",
                "content": escalation.message,
                "session_id": session_id,
                "escalation_data": {
                    "email": escalation.email,
                    "phone": escalation.phone,
                    "business_hours": escalation.business_hours,
                },
            })
            yield f"data: {data}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            escalation_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # Get chat history for context
    history = chat_sessions.get(session_id, [])

    # Check for direct close match
    confirm_keywords = ["yes", "yeah", "yep", "confirm", "close", "close chat", "sure", "ok", "okay"]
    if request.message.strip().lower() in confirm_keywords:
        if history and "type 'yes' to close" in history[-1]["content"].lower():
            add_to_history(session_id, "user", request.message)
            add_to_history(session_id, "assistant", "Chat closed.")

            await persist_message(session_id, "user", request.message, "text", user_ip, user_agent, request.page_url, client_id)
            await persist_message(session_id, "assistant", "Chat closed.", "text", page_url=request.page_url, client_id=client_id)
            await close_conversation(session_id)

            async def close_stream():
                data = json.dumps({
                    "type": "chat_closed",
                    "content": "Chat closed. Thank you for chatting with us! Have a great day.",
                    "session_id": session_id,
                })
                yield f"data: {data}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                close_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )
        elif history and "connect you with our customer support team" in history[-1]["content"].lower():
            if escalation_handler.is_working_hours():
                add_to_history(session_id, "user", request.message)
                esc_msg = "I am connecting you with our human support team now. An agent will be with you shortly."
                add_to_history(session_id, "assistant", esc_msg)

                await persist_message(session_id, "user", request.message, "text", user_ip, user_agent, request.page_url, client_id)
                await persist_message(session_id, "assistant", esc_msg, "escalation", page_url=request.page_url, client_id=client_id)

                async with async_session() as db:
                    res = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
                    conv = res.scalar_one_or_none()
                    if conv:
                        conv.status = "escalated"
                        await db.commit()
                        await broadcast({
                            "type": "conversation_escalated",
                            "conversation_id": str(conv.id),
                            "session_id": session_id,
                        })

                async def esc_stream():
                    data = json.dumps({"type": "token", "content": esc_msg, "session_id": session_id})
                    yield f"data: {data}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    esc_stream(),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )
            else:
                add_to_history(session_id, "user", request.message)
                out_msg = (
                    f"Our customer support is currently unavailable.\n\n"
                    f"🕐 **Working Hours:** {escalation_handler.business_hours}\n"
                    f"📧 **Email:** {escalation_handler.support_email}\n\n"
                    f"Please leave your query and contact details here, and our team will get back to you soon."
                )
                add_to_history(session_id, "assistant", out_msg)
                await persist_message(session_id, "user", request.message, "text", user_ip, user_agent, request.page_url, client_id)
                await persist_message(session_id, "assistant", out_msg, "text", page_url=request.page_url, client_id=client_id)

                async def out_stream():
                    data = json.dumps({"type": "token", "content": out_msg, "session_id": session_id})
                    yield f"data: {data}\n\n"
                    yield "data: [DONE]\n\n"
                return StreamingResponse(
                    out_stream(),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                )

    # Check for "no" intent (don't need more help)
    no_keywords = ["no", "no thanks", "nope", "nothing else", "no thank you", "that's it", "thanks, i'm done"]
    if request.message.strip().lower() in no_keywords:
        if history and "connect you with our customer support team" in history[-1]["content"].lower():
            confirm_msg = "Understood! Is there anything else about our services I can help you with today?"
            add_to_history(session_id, "user", request.message)
            add_to_history(session_id, "assistant", confirm_msg)

            await persist_message(session_id, "user", request.message, "text", user_ip, user_agent, request.page_url, client_id)
            await persist_message(session_id, "assistant", confirm_msg, "text", page_url=request.page_url, client_id=client_id)

            async def confirm_stream():
                data = json.dumps({"type": "token", "content": confirm_msg, "session_id": session_id})
                yield f"data: {data}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                confirm_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )

        confirm_msg = "Would you like to close this chat? Type 'yes' to close."
        add_to_history(session_id, "user", request.message)
        add_to_history(session_id, "assistant", confirm_msg)

        await persist_message(session_id, "user", request.message, "text", user_ip, user_agent, request.page_url, client_id)
        await persist_message(session_id, "assistant", confirm_msg, "text", page_url=request.page_url, client_id=client_id)

        async def confirm_stream():
            data = json.dumps({"type": "token", "content": confirm_msg, "session_id": session_id})
            yield f"data: {data}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            confirm_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # Add user message to history
    add_to_history(session_id, "user", request.message)

    # Persist user message to DB
    await persist_message(session_id, "user", request.message, "text", user_ip, user_agent, request.page_url, client_id)

    # Stream the AI response
    async def response_stream():
        full_response = ""
        try:
            for token in rag_pipeline.chat_stream(request.message, history):
                full_response += token
                data = json.dumps({
                    "type": "token",
                    "content": token,
                    "session_id": session_id,
                })
                yield f"data: {data}\n\n"
                await asyncio.sleep(0.01)

            add_to_history(session_id, "assistant", full_response)
            await persist_message(session_id, "assistant", full_response, "text", page_url=request.page_url, client_id=client_id)

        except Exception as e:
            logger.error(f"Error in chat stream: {str(e)}")
            error_msg = (
                "I'm sorry, I encountered an error. Please try again, "
                "or contact our team for assistance."
            )
            data = json.dumps({"type": "error", "content": error_msg, "session_id": session_id})
            yield f"data: {data}\n\n"
            await persist_message(session_id, "assistant", error_msg, "error", page_url=request.page_url, client_id=client_id)

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        response_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.post("/api/ingest", response_model=IngestResponse, tags=["Knowledge Base"])
async def ingest_website(request: IngestRequest, background_tasks: BackgroundTasks):
    """Ingest a website into a client's knowledge base."""
    client_id = await resolve_client_id(request.client_id)
    rag_pipeline = get_pipeline_for_client(client_id)

    if not scraper:
        raise HTTPException(status_code=503, detail="Scraper not initialized")

    logger.info(f"Ingestion requested for: {request.url} (client: {client_id})")

    try:
        documents = scraper.scrape_website(request.url)

        if not documents:
            return IngestResponse(status="warning", url=request.url, documents_scraped=0, chunks_created=0)

        chunks_created = rag_pipeline.ingest_documents(documents)

        return IngestResponse(
            status="success",
            url=request.url,
            documents_scraped=len(documents),
            chunks_created=chunks_created,
        )

    except Exception as e:
        logger.error(f"Ingestion failed for {request.url}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.post("/api/escalate", tags=["Escalation"])
async def escalate(request: EscalateRequest):
    """Manually trigger a human escalation."""
    client_id = await resolve_client_id(request.client_id)
    escalation_handler = get_escalation_for_client(client_id)

    escalation = escalation_handler.force_escalate(
        reason=request.message or "User requested escalation"
    )

    if request.session_id and request.session_id in chat_sessions:
        add_to_history(request.session_id, "assistant", escalation.message)

    return {
        "status": "escalated",
        "message": escalation.message,
        "contact": {
            "email": escalation.email,
            "phone": escalation.phone,
            "business_hours": escalation.business_hours,
        },
    }


# ─────────────────────────────────────────────
# Run with: uvicorn main:app --reload --port 8000
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
