from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import logging
import time
import json
from fastapi.responses import StreamingResponse

from app.config import settings
from app.services.llm.groq_service import get_groq_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------------
class GroqQueryRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None


class ClearSessionRequest(BaseModel):
    session_id: str


class QueryResponse(BaseModel):
    answer: str
    voice_text: Optional[str] = None
    sources: List[str]
    session_id: str
    conversation_id: Optional[str] = None
    source: str = "groq_rag"
    intent: str = "llm_generated"
    confidence: float = 0.95


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(request: Request, data: GroqQueryRequest):
    """Uses in-memory session memory for conversation context. Clears on restart."""
    start_time = time.time()
    session_id = data.session_id or "default"

    request_id = getattr(request.state, "request_id", None)
    entry = getattr(request.state, "request_entry", None)
    if entry is not None:
        entry["event"] = "qa_request"
        entry["message"] = data.message
        entry["session_id"] = session_id
        entry["conversation_id"] = data.conversation_id

    try:
        service = get_groq_service()
        result = await service.generate_response(data.message, session_id=session_id)
        _api_ms = round((time.time() - start_time) * 1000)

        # ── DEMO_SAFEPOINT: post-process ALL responses (personality, unknown replacement) ──
        if settings.demo_safepoint:
            from app.services.llm.safe_point import post_process_response

            result = post_process_response(None, data.message, result, "en")
        # ── End DEMO_SAFEPOINT post-processing ──

        response = QueryResponse(
            answer=result["answer"],
            voice_text=result.get("voice_text"),
            sources=[],
            session_id=session_id,
            conversation_id=data.conversation_id,
            source=result.get("source", "groq_rag"),
            intent=result.get(
                "intent",
                "faq_deterministic"
                if result.get("source") == "faq_deterministic"
                else "llm_generated",
            ),
        )

        # Response observability — source, confidence, answer length, total latency.
        if entry is not None:
            entry["response_source"] = response.source
            entry["confidence"] = response.confidence
            entry["answer_len"] = len(response.answer)
            entry["latency_ms"] = round((time.time() - start_time) * 1000, 2)
            entry["status"] = 200

        logger.info(
            f"QA_OK request_id={request_id} session={session_id} "
            f"source={response.source} confidence={response.confidence} "
            f"answer_len={len(response.answer)} latency_ms={round((time.time() - start_time) * 1000, 2)} "
            f"source_engine={result.get('source', '?')}"
        )
        return response
    except Exception as e:
        if entry is not None:
            entry["error"] = str(e)
            entry["status"] = 500
            entry["latency_ms"] = round((time.time() - start_time) * 1000, 2)
        logger.error(f"QA_ERR request_id={request_id} session={session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/query-stream")
async def query_stream_endpoint(request: Request, data: GroqQueryRequest):
    """
    STREAMING ENDPOINT with in-memory session memory.
    """
    entry = getattr(request.state, "request_entry", None)
    if entry is not None:
        entry["event"] = "qa_stream_request"
        entry["message"] = data.message
        entry["session_id"] = data.session_id or "default"
        entry["conversation_id"] = data.conversation_id

    try:
        session_id = data.session_id or "default"
        service = get_groq_service()

        async def stream_generator():
            full_answer = ""
            async for chunk in service.stream_response(data.message, session_id=session_id):
                full_answer += chunk
                yield f"data: {json.dumps({'text': chunk})}\n\n"

            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    except Exception as e:
        if entry is not None:
            entry["error"] = str(e)
            entry["status"] = 500
        logger.error(f"STREAM_ERR request_id={getattr(request.state, 'request_id', None)}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/debug/last-requests")
async def debug_last_requests():
    """Debug endpoint: last 100 request records in chronological order."""
    from app.services.request_log import get_request_logger

    requests = get_request_logger().snapshot()
    return {"count": len(requests), "requests": requests}


@router.post("/session/clear")
async def clear_session(data: ClearSessionRequest):
    """Clear in-memory session memory for a given session_id."""
    service = get_groq_service()
    service.clear_session(data.session_id)
    return {"status": "ok", "session_id": data.session_id}


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "BCREC Voice Brain",
        "engine": "Groq Llama 3.3",
        "groq_available": bool(settings.groq_api_key),
        "sarvam_available": bool(settings.sarvam_api_key),
    }


@router.post("/debug")
async def debug_endpoint(data: GroqQueryRequest):
    """Debug endpoint: shows lang, raw context, and cache state without LLM call."""
    service = get_groq_service()
    from app.utils.language_detect import detect_language

    lang = detect_language(data.message)
    context = service._retrieve_context(data.message)
    cache_stats = service.get_cache_stats()
    return {
        "query": data.message,
        "lang": lang,
        "context_preview": context[:500] if context else "(empty)",
        "context_len": len(context),
        "cache": cache_stats,
    }
