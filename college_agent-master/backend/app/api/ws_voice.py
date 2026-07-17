"""
WebSocket Voice Pipeline — phone-call-like streaming experience.

Single WebSocket connection handles:
  1. Client sends text query
  2. Server streams LLM tokens (for chat display)
  3. Server accumulates tokens into sentences
  4. For each complete sentence, triggers TTS in a background task
  5. Audio chunks stream back to client as they're generated

Pipeline concurrency: while sentence N's audio plays on the client,
sentence N+1's TTS is being generated on the server.
"""

import asyncio
import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.llm.groq_service import get_groq_service
from app.config import settings
from app.services.sarvam_service import get_sarvam_service, init_sarvam_service
from app.utils.language_detect import detect_language_bcp47

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/voice")
async def voice_pipeline(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket /ws/voice connected")

    service = get_groq_service()
    if settings.sarvam_api_key:
        init_sarvam_service(settings.sarvam_api_key)
    sarvam = get_sarvam_service()
    sarvam_ok = sarvam.is_available()

    try:
        data = await websocket.receive_json()

        if data.get("type") != "text":
            await websocket.send_json(
                {"type": "error", "message": "First message must be type 'text'"}
            )
            return

        query = data.get("data", "").strip()
        if not query:
            await websocket.send_json({"type": "error", "message": "Empty query"})
            return

        # Auto-detect language from query text
        lang = data.get("language") or detect_language_bcp47(query)

        # Queue connecting sentence-detection task → TTS worker
        tts_queue: asyncio.Queue = asyncio.Queue()

        # ── Background TTS worker ──────────────────────────────────────
        async def tts_worker():
            while True:
                sentence = await tts_queue.get()
                if sentence is None:
                    break
                try:
                    async for chunk in sarvam.text_to_speech_streamed(text=sentence, language=lang):
                        if chunk:
                            b64 = base64.b64encode(chunk).decode()
                            await websocket.send_json(
                                {"type": "audio", "data": b64, "format": "wav"}
                            )
                except Exception as e:
                    logger.error(f"TTS worker error: {e}")

        tts_task = asyncio.create_task(tts_worker())

        # ── Stream LLM response and detect sentence boundaries ─────────
        sentence_buffer = ""
        full_answer = ""

        async for token in service.stream_response(query):
            full_answer += token
            sentence_buffer += token

            # Send token to client for real-time text display
            await websocket.send_json({"type": "token", "data": token})

            # Sentence boundary detection
            if any(token.endswith(p) for p in (".", "!", "?", "\n")):
                sentence = sentence_buffer.strip()
                if sentence and sarvam_ok:
                    await tts_queue.put(sentence)
                sentence_buffer = ""

        # Flush remaining buffer
        remaining = sentence_buffer.strip()
        if remaining and sarvam_ok:
            await tts_queue.put(remaining)

        # Signal TTS worker to finish
        await tts_queue.put(None)
        await tts_task

        # Signal client that streaming is complete
        await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        logger.info("WebSocket /ws/voice disconnected")
    except Exception as e:
        logger.error(f"WebSocket /ws/voice error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
