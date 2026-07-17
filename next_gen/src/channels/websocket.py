"""WebSocket adapter for streaming chat."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core.models import ChannelMessage

logger = logging.getLogger(__name__)

router = APIRouter()

# Pipeline will be set by main app
_pipeline = None
_tts_engine = None


def init_websocket_adapter(pipeline, tts_engine=None):
    """Initialize the WebSocket adapter."""
    global _pipeline, _tts_engine
    _pipeline = pipeline
    _tts_engine = tts_engine


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    """WebSocket endpoint for streaming chat."""
    await websocket.accept()
    logger.info("WebSocket connected")

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "text":
                message = ChannelMessage(
                    text=data.get("data", ""),
                    session_id=data.get("session_id", "default"),
                    channel="websocket",
                )

                if not message.text:
                    await websocket.send_json({"type": "error", "message": "Empty query"})
                    continue

                # Process through pipeline
                result = await _pipeline.process(message)

                # Send response
                await websocket.send_json({
                    "type": "done",
                    "data": result.response.text,
                    "metadata": {
                        "source": result.source.value,
                        "language": result.response.language.value,
                        "latency_ms": result.latency_ms,
                    },
                })

            elif data.get("type") == "voice":
                # Voice input — for now, require text
                await websocket.send_json({
                    "type": "error",
                    "message": "Voice input not yet supported via WebSocket. Use REST API."
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
