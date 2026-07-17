"""
Phase 3 Lite - TTS Audio Cache
================================
In-memory + on-disk cache for frequently-used TTS responses.
Eliminates TTS latency on repeated utterances (greetings, contact info, etc.)

Used by: backend/app/api/tts.py
"""
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_CACHE_DIR = str(Path(__file__).resolve().parent.parent.parent.parent / "temp_audio" / "tts_cache")
_MAX_MEMORY_ENTRIES = 128

# In-memory dict: key -> raw WAV bytes
_MEMORY_CACHE: dict = {}


def _make_key(text: str, language: str, speaker: str) -> str:
    """Stable hash key for a (text, language, speaker) triple."""
    raw = f"{text.strip().lower()}|{language}|{speaker}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _disk_path(key: str) -> str:
    return os.path.join(_CACHE_DIR, f"{key}.wav")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_cached_audio(text: str, language: str, speaker: str) -> Optional[bytes]:
    """Return cached WAV bytes or None if not cached."""
    key = _make_key(text, language, speaker)

    # 1. Memory hit
    if key in _MEMORY_CACHE:
        logger.debug(f"TTS cache MEMORY HIT: {key[:8]}")
        return _MEMORY_CACHE[key]

    # 2. Disk hit
    path = _disk_path(key)
    if os.path.isfile(path):
        try:
            with open(path, "rb") as f:
                data = f.read()
            # Warm memory cache
            if len(_MEMORY_CACHE) < _MAX_MEMORY_ENTRIES:
                _MEMORY_CACHE[key] = data
            logger.debug(f"TTS cache DISK HIT: {key[:8]} ({len(data)} bytes)")
            return data
        except Exception as e:
            logger.warning(f"TTS cache disk read failed: {e}")

    return None


def store_audio(text: str, language: str, speaker: str, audio_bytes: bytes) -> None:
    """Store WAV bytes in memory and disk cache."""
    key = _make_key(text, language, speaker)

    # Memory
    if len(_MEMORY_CACHE) < _MAX_MEMORY_ENTRIES:
        _MEMORY_CACHE[key] = audio_bytes

    # Disk
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        path = _disk_path(key)
        with open(path, "wb") as f:
            f.write(audio_bytes)
        logger.debug(f"TTS cache stored: {key[:8]} ({len(audio_bytes)} bytes)")
    except Exception as e:
        logger.warning(f"TTS cache disk write failed: {e}")


def get_stats() -> dict:
    """Return cache statistics."""
    disk_files = 0
    disk_bytes = 0
    if os.path.isdir(_CACHE_DIR):
        for fname in os.listdir(_CACHE_DIR):
            if fname.endswith(".wav"):
                disk_files += 1
                try:
                    disk_bytes += os.path.getsize(os.path.join(_CACHE_DIR, fname))
                except Exception:
                    pass
    return {
        "memory_entries": len(_MEMORY_CACHE),
        "memory_max": _MAX_MEMORY_ENTRIES,
        "disk_files": disk_files,
        "disk_bytes": disk_bytes,
        "cache_dir": _CACHE_DIR,
    }
