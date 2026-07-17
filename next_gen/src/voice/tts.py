"""Text-to-speech using edge-tts (Microsoft, free)."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import AsyncIterator

from ..core.models import Language

logger = logging.getLogger(__name__)

# Voice mapping for each language
_VOICE_MAP = {
    Language.EN: "en-US-AriaNeural",
    Language.HI: "hi-IN-SwaraNeural",
    Language.BN: "bn-BN-TanishaaNeural",
}


class TTSEngine:
    """Text-to-speech engine using edge-tts."""

    def __init__(self):
        self._available = False
        try:
            import edge_tts
            self._available = True
        except ImportError:
            logger.warning("edge-tts not installed. TTS disabled.")

    @property
    def is_available(self) -> bool:
        return self._available

    async def synthesize(self, text: str, lang: Language) -> bytes | None:
        """Synthesize text to audio bytes (MP3)."""
        if not self._available:
            return None

        try:
            import edge_tts
            voice = _VOICE_MAP.get(lang, _VOICE_MAP[Language.EN])
            communicate = edge_tts.Communicate(text, voice)
            audio_data = io.BytesIO()

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.write(chunk["data"])

            return audio_data.getvalue()
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None

    async def synthesize_stream(self, text: str, lang: Language) -> AsyncIterator[bytes]:
        """Stream audio chunks."""
        if not self._available:
            return

        try:
            import edge_tts
            voice = _VOICE_MAP.get(lang, _VOICE_MAP[Language.EN])
            communicate = edge_tts.Communicate(text, voice)

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        except Exception as e:
            logger.error(f"TTS stream error: {e}")
