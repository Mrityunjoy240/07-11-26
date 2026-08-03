"""
Sarvam Agents SDK bridge — communication layer (Bridge mode / Architecture A).

This backend hosts an ``AsyncSamvaadAgent`` that connects to Sarvam's
app-runtime over WebSocket. The Sarvam platform agent handles the telephony /
voice channel with the user; this service is the client side of that bridge:

    user speech  ->  Sarvam STT  ->  transcript_callback  ->  POST /qa/query
    answer       <-  /qa/query   <-  our intelligence      <-  Groq + RAG
    answer       ->  agent.send_text(answer)  ->  Sarvam agent speaks it

Agent variables are ALWAYS real, validated values (session_id, user_identifier,
caller_type, query_topic, language) — never unresolved template strings such as
``{{user.message}}``.

Environment / Settings used:
    SARVAM_API_KEY        (required)
    SARVAM_ORG_ID         (required)
    SARVAM_WORKSPACE_ID   (required)
    SARVAM_APP_ID         (required)
    SARVAM_BASE_URL       (optional, default https://apps.sarvam.ai/api/app-runtime/)
    SARVAM_QA_ENDPOINT    (optional, default http://127.0.0.1:8000/qa/query)
    SARVAM_CONNECT_TIMEOUT(optional seconds, default 10.0)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Optional
from uuid import uuid4

import httpx
from pydantic import SecretStr

from app.config import settings
from app.services.request_log import record_request

logger = logging.getLogger(__name__)

try:  # Import submodules directly to avoid pulling in default_audio_interface
    from sarvam_conv_ai_sdk.conversation import AsyncSamvaadAgent
    from sarvam_conv_ai_sdk.messages.config import InteractionConfig
    from sarvam_conv_ai_sdk.messages.events import (
        ServerEventBase,
        ServerInteractionConnectedEvent,
        ServerInteractionEndEvent,
    )
    from sarvam_conv_ai_sdk.messages.text import (
        ServerTextChunkMsg,
        ServerTextMsg,
        ServerTranscriptMsg,
        ServerTextMsgType,
    )
    from sarvam_conv_ai_sdk.messages.types import (
        InteractionType,
        Role,
        UserIdentifierType,
    )
    from sarvam_conv_ai_sdk.tool import SarvamToolLanguageName

    SARVAM_SDK_AVAILABLE = True
except Exception as e:  # noqa: BLE001
    SARVAM_SDK_AVAILABLE = False
    AsyncSamvaadAgent = None  # type: ignore[assignment]
    InteractionConfig = None  # type: ignore[assignment]
    InteractionType = None  # type: ignore[assignment]
    Role = None  # type: ignore[assignment]
    UserIdentifierType = None  # type: ignore[assignment]
    SarvamToolLanguageName = None  # type: ignore[assignment]
    logger.warning("sarvam-conv-ai-sdk not available: %s", e)


@dataclass
class SarvamSDKConfig:
    """Configuration for the Sarvam Agents SDK bridge.

    Values are read from app settings (which in turn read environment
    variables), so nothing is hardcoded. ``is_configured()`` is the single
    readiness gate used before creating any session.
    """

    api_key: str = ""
    org_id: str = ""
    workspace_id: str = ""
    app_id: str = ""
    base_url: str = "https://apps.sarvam.ai/api/app-runtime/"
    qa_endpoint: str = "http://127.0.0.1:8000/qa/query"
    sample_rate: int = 16000
    connect_timeout: float = 10.0
    default_language: str = "English"

    @classmethod
    def from_settings(cls) -> "SarvamSDKConfig":
        import os

        return cls(
            api_key=settings.sarvam_api_key,
            org_id=settings.sarvam_org_id,
            workspace_id=settings.sarvam_workspace_id,
            app_id=settings.sarvam_app_id,
            base_url=os.getenv(
                "SARVAM_BASE_URL", "https://apps.sarvam.ai/api/app-runtime/"
            ),
            qa_endpoint=os.getenv(
                "SARVAM_QA_ENDPOINT", "http://127.0.0.1:8000/qa/query"
            ),
            connect_timeout=float(os.getenv("SARVAM_CONNECT_TIMEOUT", "10.0")),
        )

    def is_configured(self) -> bool:
        return bool(self.api_key and self.org_id and self.workspace_id and self.app_id)


@dataclass
class SarvamSDKCall:
    """An active SDK bridge session."""

    session_id: str
    user_identifier: str
    language: str = "English"
    user_identifier_type: UserIdentifierType = UserIdentifierType.CUSTOM
    agent: Optional[Any] = None
    interaction_id: Optional[str] = None
    status: str = "connecting"  # connecting|connected|disconnected|stopped|error
    error: Optional[str] = None
    message_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_active: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_identifier": self.user_identifier,
            "user_identifier_type": self.user_identifier_type.value,
            "language": self.language,
            "interaction_id": self.interaction_id,
            "status": self.status,
            "error": self.error,
            "message_count": self.message_count,
            "created_at": self.created_at,
            "last_active": self.last_active,
        }


_LANGUAGE_NAMES = (
    {lang.value.lower(): lang for lang in SarvamToolLanguageName}
    if SARVAM_SDK_AVAILABLE and SarvamToolLanguageName is not None
    else {}
)

_IDENTIFIER_TYPES = (
    {
        "custom": UserIdentifierType.CUSTOM,
        "phone_number": UserIdentifierType.PHONE_NUMBER,
        "email": UserIdentifierType.EMAIL,
        "unknown": UserIdentifierType.UNKNOWN,
    }
    if SARVAM_SDK_AVAILABLE and UserIdentifierType is not None
    else {}
)


class SarvamSDKService:
    """Bridge between Sarvam Agents SDK and the existing /qa/query endpoint.

    Lifecycle contract:
        * ``create_session`` builds an ``InteractionConfig`` with real agent
          variables, starts the ``AsyncSamvaadAgent`` and waits for connect.
        * User speech arrives on ``transcript_callback`` (role=user) and is
          forwarded to ``/qa/query``; the answer is delivered back to the
          user through the agent via ``agent.send_text``.
        * ``stop_session`` / ``stop_all`` always call ``await agent.stop()``
          in a ``finally`` block.
    """

    def __init__(self, config: Optional[SarvamSDKConfig] = None) -> None:
        self.config = config or SarvamSDKConfig.from_settings()
        self._sessions: dict[str, SarvamSDKCall] = {}
        self._lock = asyncio.Lock()
        self._http: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def is_available(self) -> bool:
        return SARVAM_SDK_AVAILABLE and self.config.is_configured()

    async def create_session(
        self,
        user_identifier: str,
        user_identifier_type: str = "custom",
        language: str = "English",
        query_topic: str = "general",
        caller_type: str = "caller",
    ) -> SarvamSDKCall:
        """Create and start a bridge session for one user interaction."""
        if not SARVAM_SDK_AVAILABLE:
            raise RuntimeError("sarvam-conv-ai-sdk is not installed")
        if not self.config.is_configured():
            raise RuntimeError(
                "Sarvam SDK not configured: SARVAM_API_KEY, SARVAM_ORG_ID, "
                "SARVAM_WORKSPACE_ID and SARVAM_APP_ID are all required"
            )

        session_id = str(uuid4())
        identifier = user_identifier or f"sarvam-{session_id[:8]}"
        lang = _LANGUAGE_NAMES.get(language.lower(), SarvamToolLanguageName.ENGLISH)
        id_type = _IDENTIFIER_TYPES.get(
            (user_identifier_type or "custom").lower(), UserIdentifierType.CUSTOM
        )

        # Agent variables are ALWAYS real values. Never unresolved templates.
        agent_variables = {
            "session_id": session_id,
            "user_identifier": identifier,
            "caller_type": caller_type or "caller",
            "query_topic": query_topic or "general",
            "language": language or "English",
        }

        config = InteractionConfig(
            user_identifier_type=id_type,
            user_identifier=identifier,
            org_id=self.config.org_id,
            workspace_id=self.config.workspace_id,
            app_id=self.config.app_id,
            interaction_type=InteractionType.CALL,
            agent_variables=agent_variables,
            initial_language_name=lang,
            sample_rate=self.config.sample_rate,
        )

        call = SarvamSDKCall(
            session_id=session_id,
            user_identifier=identifier,
            language=language or "English",
            user_identifier_type=id_type,
        )

        agent = AsyncSamvaadAgent(
            api_key=SecretStr(self.config.api_key),
            config=config,
            transcript_callback=self._make_transcript_callback(session_id),
            text_callback=self._make_text_callback(session_id),
            event_callback=self._make_event_callback(session_id),
            base_url=self.config.base_url,
        )
        call.agent = agent

        async with self._lock:
            self._sessions[session_id] = call

        entry = {
            "event": "sarvam_sdk_session_start",
            "session_id": session_id,
            "user_identifier": identifier,
            "user_identifier_type": id_type.value,
            "language": call.language,
            "app_id": self.config.app_id,
        }

        try:
            await agent.start()
            connected = await agent.wait_for_connect(timeout=self.config.connect_timeout)
            if not connected:
                call.status = "connecting"
                call.error = "wait_for_connect timed out"
                entry["status"] = 202
                entry["error"] = call.error
            else:
                call.status = "connected"
                call.interaction_id = agent.get_interaction_id()
                entry["status"] = 200
            entry["interaction_id"] = call.interaction_id
            logger.info(
                "SDK_SESSION start session=%s user=%s connected=%s",
                session_id, identifier, connected,
            )
        except Exception as e:  # noqa: BLE001
            call.status = "error"
            call.error = str(e)
            entry["status"] = 500
            entry["error"] = str(e)
            logger.error("SDK_SESSION start failed session=%s: %s", session_id, e)
            await self._safe_stop(agent)
        finally:
            record_request(entry)

        return call

    async def forward_message(self, session_id: str, text: str) -> Optional[str]:
        """Inject a user message into an existing session.

        Forwards the text to /qa/query and delivers the answer through the
        agent. Returns the answer text, or None if the session is unknown.
        """
        call = await self.get_session(session_id)
        if call is None:
            return None
        return await self._forward_to_qa(call, text)

    async def stop_session(self, session_id: str, reason: str = "user_request") -> None:
        """Stop one session; always cleans up the agent WebSocket."""
        async with self._lock:
            call = self._sessions.pop(session_id, None)
        if call is None:
            return

        entry = {
            "event": "sarvam_sdk_session_stop",
            "session_id": session_id,
            "user_identifier": call.user_identifier,
            "reason": reason,
            "message_count": call.message_count,
        }
        try:
            await self._safe_stop(call.agent)
            call.status = "stopped"
            entry["status"] = 200
        except Exception as e:  # noqa: BLE001
            call.status = "error"
            call.error = str(e)
            entry["status"] = 500
            entry["error"] = str(e)
            logger.error("SDK_SESSION stop failed session=%s: %s", session_id, e)
        finally:
            record_request(entry)
        logger.info("SDK_SESSION stop session=%s reason=%s", session_id, reason)

    async def stop_all(self) -> None:
        """Stop every active session (app shutdown hook)."""
        async with self._lock:
            ids = list(self._sessions.keys())
        for sid in ids:
            await self.stop_session(sid, reason="server_shutdown")
        if self._http is not None:
            try:
                await self._http.aclose()
            except Exception:  # noqa: BLE001
                pass
            self._http = None
        logger.info("SDK_ALL sessions stopped (%d)", len(ids))

    async def reconnect(self, session_id: str) -> Optional[SarvamSDKCall]:
        """Re-establish a stopped/failed session with the same identifiers."""
        call = await self.get_session(session_id)
        if call is None or call.agent is None:
            return None
        await self._safe_stop(call.agent)
        call.status = "connecting"
        call.error = None
        try:
            await call.agent.start()
            connected = await call.agent.wait_for_connect(timeout=self.config.connect_timeout)
            call.status = "connected" if connected else "connecting"
            call.interaction_id = call.agent.get_interaction_id()
            record_request({
                "event": "sarvam_sdk_session_reconnect",
                "session_id": session_id,
                "connected": connected,
            })
        except Exception as e:  # noqa: BLE001
            call.status = "error"
            call.error = str(e)
            record_request({
                "event": "sarvam_sdk_session_reconnect",
                "session_id": session_id,
                "status": 500,
                "error": str(e),
            })
            logger.error("SDK_SESSION reconnect failed session=%s: %s", session_id, e)
        return call

    async def get_session(self, session_id: str) -> Optional[SarvamSDKCall]:
        async with self._lock:
            call = self._sessions.get(session_id)
            if call is None:
                return None
            return call

    async def list_sessions(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [c.summary() for c in self._sessions.values()]

    def health(self) -> dict[str, Any]:
        return {
            "sdk_available": SARVAM_SDK_AVAILABLE,
            "configured": self.config.is_configured(),
            "app_id": self.config.app_id,
            "org_id": self.config.org_id,
            "workspace_id": self.config.workspace_id,
            "active_sessions": len(self._sessions),
        }

    # ------------------------------------------------------------------ #
    # Internal — SDK callbacks
    # ------------------------------------------------------------------ #
    def _make_transcript_callback(self, session_id: str):
        async def _cb(msg: ServerTranscriptMsg) -> None:
            if msg.role != Role.USER:
                return
            call = await self.get_session(session_id)
            if call is None:
                return
            call.message_count += 1
            call.last_active = datetime.now(UTC).isoformat()
            text = (msg.content or "").strip()
            if not text:
                return
            logger.info("SDK_TRANSCRIPT session=%s user_said=%r", session_id, text[:80])
            await self._forward_to_qa(call, text)

        return _cb

    def _make_text_callback(self, session_id: str):
        async def _cb(msg: ServerTextMsgType) -> None:
            # Text from the platform agent (relayed agent wording). Logged for
            # telemetry only — our answers come from /qa/query, not from the
            # platform LLM, so we never loop this back.
            text = msg.text if isinstance(msg, (ServerTextMsg, ServerTextChunkMsg)) else str(msg)
            logger.info("SDK_AGENT_TEXT session=%s text=%r", session_id, text[:80])

        return _cb

    def _make_event_callback(self, session_id: str):
        async def _cb(event: ServerEventBase) -> None:
            if isinstance(event, ServerInteractionConnectedEvent):
                call = await self.get_session(session_id)
                if call is not None:
                    call.interaction_id = event.interaction_id
                    call.status = "connected"
                    call.last_active = datetime.now(UTC).isoformat()
                    record_request({
                        "event": "sarvam_sdk_interaction_connected",
                        "session_id": session_id,
                        "interaction_id": event.interaction_id,
                        "status": 200,
                    })
                    logger.info(
                        "SDK_EVENT connected session=%s id=%s",
                        session_id, event.interaction_id,
                    )
            elif isinstance(event, ServerInteractionEndEvent):
                call = await self.get_session(session_id)
                if call is not None:
                    call.status = "disconnected"
                    call.last_active = datetime.now(UTC).isoformat()
                record_request({
                    "event": "sarvam_sdk_interaction_end",
                    "session_id": session_id,
                    "status": 200,
                })
                logger.info("SDK_EVENT interaction ended session=%s", session_id)
            else:
                logger.debug("SDK_EVENT session=%s event=%s", session_id, type(event).__name__)

        return _cb

    # ------------------------------------------------------------------ #
    # Internal — forwarding + delivery
    # ------------------------------------------------------------------ #
    def _http_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=120.0)
        return self._http

    async def _forward_to_qa(self, call: SarvamSDKCall, text: str) -> Optional[str]:
        """POST the user message to the existing /qa/query endpoint.

        The answer is delivered back to the user through the agent. Telemetry
        is recorded in the same request_log used by /qa/query itself.
        """
        start = time.time()
        entry = {
            "event": "sarvam_sdk_forward",
            "session_id": call.session_id,
            "user_identifier": call.user_identifier,
            "message": text,
            "intent": "sarvam_sdk_bridge",
        }
        try:
            resp = await self._http_client().post(
                self.config.qa_endpoint,
                json={
                    "message": text,
                    "session_id": call.session_id,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            answer = (data.get("answer") or "").strip()
            entry.update({
                "status": resp.status_code,
                "response_source": data.get("source"),
                "confidence": data.get("confidence"),
                "answer_len": len(answer),
                "latency_ms": round((time.time() - start) * 1000, 2),
            })
            record_request(entry)
            logger.info(
                "SDK_FORWARD session=%s source=%s len=%d",
                call.session_id, data.get("source"), len(answer),
            )

            if answer:
                delivered = await self._deliver_answer(call, answer)
                record_request({
                    "event": "sarvam_sdk_deliver",
                    "session_id": call.session_id,
                    "delivered": delivered,
                    "answer_len": len(answer),
                })
            return answer
        except Exception as e:  # noqa: BLE001
            entry.update({
                "status": 500,
                "error": str(e),
                "latency_ms": round((time.time() - start) * 1000, 2),
            })
            record_request(entry)
            logger.error("SDK_FORWARD failed session=%s: %s", call.session_id, e)
            return None

    async def _deliver_answer(self, call: SarvamSDKCall, answer: str) -> bool:
        """Send the answer through the agent so the platform agent speaks it."""
        agent = call.agent
        if agent is None or not agent.is_connected():
            logger.warning("SDK_DELIVER skipped session=%s (agent not connected)", call.session_id)
            return False
        try:
            await agent.send_text(answer)
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("SDK_DELIVER failed session=%s: %s", call.session_id, e)
            return False

    async def _safe_stop(self, agent: Optional[Any]) -> None:
        """Idempotent agent cleanup — always awaited, never raises."""
        if agent is None:
            return
        try:
            await agent.stop()
        except Exception as e:  # noqa: BLE001
            logger.warning("SDK agent stop raised (ignored): %s", e)


_sdk_service: Optional[SarvamSDKService] = None


def get_sarvam_sdk_service() -> SarvamSDKService:
    """Module-level singleton for the Sarvam SDK bridge service."""
    global _sdk_service
    if _sdk_service is None:
        _sdk_service = SarvamSDKService()
    return _sdk_service
