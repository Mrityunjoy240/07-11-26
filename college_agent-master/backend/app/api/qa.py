from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
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
    """Contract for /qa/query — also the target of the Sarvam HTTPS tool.

    Production voice path: Phone Call -> Sarvam Inbound Deployment -> Agent
    Runtime -> HTTP tool -> POST /qa/query -> Groq + Hybrid RAG -> HTTP
    Response -> Sarvam TTS -> Caller.

    ``message`` carries the caller's latest utterance. Session context is
    accepted as optional fields so the Sarvam agent can pass through whatever
    it has (agent variables from its OnStart/OnEnd hooks and telephony
    metadata). Unknown fields are ignored so the tool body template can be
    generous.
    """

    model_config = ConfigDict(extra="ignore")

    message: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    # -- Sarvam HTTP tool session context (all optional) --
    language: Optional[str] = None
    caller_phone: Optional[str] = None
    user_identifier: Optional[str] = None
    caller_type: Optional[str] = None
    query_topic: Optional[str] = None


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
    # -- Grounding telemetry (filled when RAG retrieval runs) --
    retrieval_score: Optional[float] = None
    documents_used: Optional[int] = None
    source_file: Optional[List[str]] = None
    chunk_ids: Optional[List[str]] = None
    retrieval_used: Optional[bool] = None
    confidence_tier: Optional[str] = None


# ---------------------------------------------------------------------------
# AUTH (Sarvam HTTPS tool)
# ---------------------------------------------------------------------------
async def require_tool_auth(request: Request) -> None:
    """Fail-closed shared-secret guard for /qa/query and conversation APIs.

    The Sarvam HTTPS tool presents it as ``Authorization: Bearer <token>`` or
    ``X-API-Key: <token>``. If ``settings.sarvam_tool_api_token`` is not set,
    the endpoint returns 503 instead of silently allowing open access: a
    misconfigured deployment must fail loudly, never expose data.
    """
    token = settings.sarvam_tool_api_token
    if not token:
        raise HTTPException(
            status_code=503,
            detail="SARVAM_TOOL_API_TOKEN not configured; refusing open access",
        )
    auth_header = request.headers.get("authorization", "")
    api_key_header = request.headers.get("x-api-key", "")
    presented = ""
    if auth_header.lower().startswith("bearer "):
        presented = auth_header[len("bearer "):].strip()
    elif api_key_header:
        presented = api_key_header.strip()
    if not presented or presented != token:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------


@router.post("/query", response_model=QueryResponse, dependencies=[Depends(require_tool_auth)])
async def query_endpoint(request: Request, data: GroqQueryRequest):
    """Uses in-memory session memory for conversation context. Clears on restart.

    Also the production Sarvam HTTPS-tool contract: the caller's utterance is
    ``message`` and session context (session_id, language, caller_phone,
    caller_type, query_topic) is passed through from the agent's variables.
    """
    start_time = time.time()
    session_id = data.session_id or "default"

    request_id = getattr(request.state, "request_id", None)

    if not data.message or not data.message.strip():
        logger.warning(
            "QA_EMPTY request_id=%s session=%s channel=tool", request_id, session_id
        )
        raise HTTPException(status_code=400, detail="message is empty")

    entry = getattr(request.state, "request_entry", None)
    if entry is not None:
        entry["event"] = "qa_request"
        entry["message"] = data.message
        entry["session_id"] = session_id
        entry["conversation_id"] = data.conversation_id
        # Sarvam tool session context — surfaced for call-level debugging.
        if data.language:
            entry["language"] = data.language
        if data.caller_phone:
            entry["caller_phone"] = data.caller_phone
        if data.user_identifier:
            entry["user_identifier"] = data.user_identifier
        if data.caller_type:
            entry["caller_type"] = data.caller_type
        if data.query_topic:
            entry["query_topic"] = data.query_topic

    try:
        service = get_groq_service()
        result = await service.generate_response(data.message, session_id=session_id)
        _api_ms = round((time.time() - start_time) * 1000)

        # ── DEMO_SAFEPOINT: post-process ALL responses (personality, unknown replacement) ──
        if settings.demo_safepoint:
            from app.services.llm.safe_point import post_process_response
            from app.utils.language_detect import detect_language

            detected_lang = detect_language(data.message)
            result = post_process_response(None, data.message, result, detected_lang)
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
            retrieval_score=result.get("retrieval_score"),
            documents_used=result.get("documents_used"),
            source_file=result.get("source_file"),
            chunk_ids=result.get("chunk_ids"),
            retrieval_used=result.get("retrieval_used"),
            confidence_tier=result.get("confidence_tier"),
        )

        # Response observability — source, confidence, answer length, total latency.
        if entry is not None:
            entry["response_source"] = response.source
            entry["confidence"] = response.confidence
            entry["answer_len"] = len(response.answer)
            entry["latency_ms"] = round((time.time() - start_time) * 1000, 2)
            entry["status"] = 200
            # Grounding observability — retrieval score, docs used, sources, chunk ids.
            if response.retrieval_score is not None:
                entry["retrieval_score"] = response.retrieval_score
                entry["documents_used"] = response.documents_used
                entry["source_file"] = response.source_file
                entry["chunk_ids"] = response.chunk_ids
                entry["retrieval_used"] = response.retrieval_used
                entry["confidence_tier"] = response.confidence_tier

        logger.info(
            f"QA_OK request_id={request_id} session={session_id} "
            f"source={response.source} confidence={response.confidence} "
            f"answer_len={len(response.answer)} latency_ms={round((time.time() - start_time) * 1000, 2)} "
            f"source_engine={result.get('source', '?')} "
            f"retrieval_score={response.retrieval_score} docs_used={response.documents_used} "
            f"sources={response.source_file} tier={response.confidence_tier}"
        )
        return response
    except Exception as e:
        if entry is not None:
            entry["error"] = str(e)
            entry["status"] = 500
            entry["latency_ms"] = round((time.time() - start_time) * 1000, 2)
        logger.error(f"QA_ERR request_id={request_id} session={session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/query-stream", dependencies=[Depends(require_tool_auth)])
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


@router.get("/debug/last-requests", dependencies=[Depends(require_tool_auth)])
async def debug_last_requests():
    """Debug endpoint: last 100 request records in chronological order."""
    from app.services.request_log import get_request_logger

    requests = get_request_logger().snapshot()
    return {"count": len(requests), "requests": requests}


@router.post("/session/clear", dependencies=[Depends(require_tool_auth)])
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
        "telephony_channel": "sarvam_inbound_http_tool",
        "sdk_enabled": settings.sarvam_sdk_enabled,
        "tool_auth_configured": bool(settings.sarvam_tool_api_token),
    }


@router.post("/debug", dependencies=[Depends(require_tool_auth)])
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
