"""
Sarvam Agents SDK bridge router.

Exposes a thin control surface for the SDK bridge service so sessions can be
created, inspected, exercised, and torn down — without touching any QA logic.
The actual intelligence lives in the existing /qa/query endpoint; this router
only manages the AsyncSamvaadAgent communication layer.

Endpoints (all under /sdk):
    POST   /sdk/sessions                     create a bridge session
    GET    /sdk/sessions                     list sessions
    GET    /sdk/sessions/{session_id}        session status
    POST   /sdk/sessions/{session_id}/stop   stop a session
    POST   /sdk/sessions/{session_id}/message   inject a user message
    GET    /sdk/status                       config + readiness
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from app.services.sarvam_sdk import get_sarvam_sdk_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------------
class CreateSessionRequest(BaseModel):
    user_identifier: Optional[str] = None
    user_identifier_type: str = "custom"
    language: str = "English"
    query_topic: str = "general"
    caller_type: str = "caller"


class MessageRequest(BaseModel):
    message: str


class StopSessionRequest(BaseModel):
    reason: str = "user_request"


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------
@router.post("/sessions", status_code=201)
async def create_session(data: CreateSessionRequest):
    service = get_sarvam_sdk_service()
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Sarvam SDK bridge unavailable: SDK not installed or "
                "SARVAM_API_KEY/SARVAM_ORG_ID/SARVAM_WORKSPACE_ID/SARVAM_APP_ID "
                "not configured"
            ),
        )
    try:
        call = await service.create_session(
            user_identifier=data.user_identifier or "",
            user_identifier_type=data.user_identifier_type,
            language=data.language,
            query_topic=data.query_topic,
            caller_type=data.caller_type,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("SDK create session error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"session": call.summary()}


@router.get("/sessions")
async def list_sessions():
    service = get_sarvam_sdk_service()
    sessions = await service.list_sessions()
    return {"count": len(sessions), "sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    service = get_sarvam_sdk_service()
    call = await service.get_session(session_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": call.summary()}


@router.post("/sessions/{session_id}/stop")
async def stop_session(session_id: str, data: Optional[StopSessionRequest] = None):
    service = get_sarvam_sdk_service()
    call = await service.get_session(session_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await service.stop_session(session_id, reason=(data.reason if data else "user_request"))
    return {"status": "stopped", "session_id": session_id}


@router.post("/sessions/{session_id}/message")
async def forward_message(session_id: str, data: MessageRequest):
    """Inject a user message into a live session (bridge test path).

    Forwards to /qa/query and delivers the answer through the agent.
    """
    service = get_sarvam_sdk_service()
    call = await service.get_session(session_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not data.message.strip():
        raise HTTPException(status_code=400, detail="message is empty")
    answer = await service.forward_message(session_id, data.message)
    return {
        "session_id": session_id,
        "message": data.message,
        "answer": answer or "",
        "status": call.status,
    }


@router.get("/status")
async def sdk_status():
    service = get_sarvam_sdk_service()
    return service.health()
