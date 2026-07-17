from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import logging
import time
import json
from datetime import datetime
from fastapi.responses import StreamingResponse

from app.config import settings
from app.database import get_db
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
# HELPERS (DB Management)
# ---------------------------------------------------------------------------
async def _get_history(conversation_id: str, limit: int = 6):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
        (conversation_id, limit)
    )
    messages = cursor.fetchall()
    conn.close()
    return [{"role": m["role"], "content": m["content"]} for m in reversed(messages)]

async def _save_turn(conversation_id: str, user_msg: str, assistant_msg: str):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    # Save User
    cursor.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, "user", user_msg, now)
    )
    # Save Assistant
    cursor.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, "assistant", assistant_msg, now)
    )
    # Update Conversation Timestamp
    cursor.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@router.post("/query", response_model=QueryResponse)
async def query_endpoint(request: Request, data: GroqQueryRequest):
    """Legacy blocking endpoint - maintained for simple compatibility."""
    start_time = time.time()
    session_id = data.session_id or "default"
    
    try:
        history = await _get_history(data.conversation_id) if data.conversation_id else None
        service = get_groq_service()
        
        result = await service.generate_response(data.message, history)
        
        if data.conversation_id:
            await _save_turn(data.conversation_id, data.message, result["answer"])
            
        return QueryResponse(
            answer=result["answer"],
            voice_text=result.get("voice_text"),
            sources=[],
            session_id=session_id,
            conversation_id=data.conversation_id,
            source=result.get("source", "groq_rag"),
            intent=result.get("intent", "faq_deterministic" if result.get("source") == "faq_deterministic" else "llm_generated")
        )
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/query-stream")
async def query_stream_endpoint(data: GroqQueryRequest):
    """
    PROFESSIONAL STREAMING ENDPOINT.
    Used by the Web UI for word-by-word rendering and tables.
    """
    try:
        history = await _get_history(data.conversation_id) if data.conversation_id else None
        service = get_groq_service()
        
        async def stream_generator():
            full_answer = ""
            async for chunk in service.stream_response(data.message, history):
                full_answer += chunk
                yield f"data: {json.dumps({'text': chunk})}\n\n"
            
            if data.conversation_id:
                await _save_turn(data.conversation_id, data.message, full_answer)
            
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Stream error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/health")
async def health():
    return {"status": "healthy", "service": "BCREC Voice Brain", "engine": "Groq Llama 3.3"}
