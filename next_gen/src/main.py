"""Next-Gen College AI Receptionist — Main Application."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.pipeline import ConversationPipeline
from src.core.intent import IntentRouter
from src.core.postprocessors import PostProcessor
from src.handlers.fee import FeeHandler
from src.handlers.contact import ContactHandler
from src.handlers.department import (
    DepartmentHandler,
    HODHandler,
    PlacementHandler,
    HostelHandler,
    ScholarshipHandler,
    ChatHandler,
)
from src.llm.groq import GroqProvider
from src.llm.router import LLMRouter
from src.retrieval.rag import RAGEngine
from src.retrieval.vector import get_vector_store
from src.session.memory import MemorySessionStore
from src.voice.tts import TTSEngine
from src.channels.rest import router as rest_router, init_rest_adapter
from src.channels.websocket import router as ws_router, init_websocket_adapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="BCREC AI Receptionist",
        version="1.0.0",
        description="AI-powered college receptionist for Dr. B.C. Roy Engineering College",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Initialize components ──────────────────────────────────────────

    # Session store
    session_store = MemorySessionStore(max_age_seconds=1800)

    # Intent router
    intent_router = IntentRouter()

    # Handlers
    handlers = [
        FeeHandler(),
        ContactHandler(),
        DepartmentHandler(),
        HODHandler(),
        PlacementHandler(),
        HostelHandler(),
        ScholarshipHandler(),
        ChatHandler(),
    ]

    # LLM
    llm_providers = []
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        llm_providers.append(GroqProvider(api_key=groq_key))
    else:
        logger.warning("GROQ_API_KEY not set. LLM features disabled.")

    llm_router = LLMRouter(llm_providers)

    # Vector store + RAG
    vector_store = get_vector_store()
    rag_engine = RAGEngine(vector_store, llm_router)

    # Post-processor
    post_processor = PostProcessor()

    # TTS
    tts_engine = TTSEngine()

    # Pipeline
    pipeline = ConversationPipeline(
        session_store=session_store,
        intent_router=intent_router,
        structured_handlers=handlers,
        rag_engine=rag_engine,
        post_processor=post_processor,
    )

    # ── Register routes ────────────────────────────────────────────────

    init_rest_adapter(pipeline)
    init_websocket_adapter(pipeline, tts_engine)

    app.include_router(rest_router, prefix="/api")
    app.include_router(ws_router)

    # ── Static files (frontend) ────────────────────────────────────────

    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    # ── Startup/shutdown events ────────────────────────────────────────

    @app.on_event("startup")
    async def startup():
        logger.info("BCREC AI Receptionist started")
        logger.info(f"LLM provider: {llm_router.name}")
        logger.info(f"TTS available: {tts_engine.is_available}")

    @app.on_event("shutdown")
    async def shutdown():
        logger.info("BCREC AI Receptionist shutting down")

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
