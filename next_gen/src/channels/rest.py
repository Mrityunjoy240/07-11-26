"""REST API adapter for text chat."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.models import ChannelMessage, Language

logger = logging.getLogger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    message: str
    session_id: str = "default"
    language: str | None = None


class QueryResponse(BaseModel):
    answer: str
    source: str
    language: str
    latency_ms: int
    session_id: str


# These will be set by the main app
_pipeline = None


def init_rest_adapter(pipeline):
    """Initialize the REST adapter with the pipeline."""
    global _pipeline
    _pipeline = pipeline


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(data: QueryRequest):
    """Handle a text query."""
    if not _pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    # Parse language
    lang = None
    if data.language:
        try:
            lang = Language(data.language)
        except ValueError:
            pass

    message = ChannelMessage(
        text=data.message,
        session_id=data.session_id,
        channel="rest",
        language=lang,
    )

    result = await _pipeline.process(message)

    return QueryResponse(
        answer=result.response.text,
        source=result.source.value,
        language=result.response.language.value,
        latency_ms=result.latency_ms,
        session_id=data.session_id,
    )


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}
