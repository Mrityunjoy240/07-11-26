"""
Language Detection Utility for BCREC Voice Agent

Uses FastText's pre-trained language identification model (lid.176.ftz)
for accurate detection of English, Hindi, and Bengali — including
code-mixed "Hinglish" and "Banglish" that regex-based approaches miss.

Model size: 917KB, loads in <100ms, 95%+ accuracy on mixed-script text.
"""
import logging
import os
import re
import urllib.request
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# Lazy-loaded model reference
_model = None
_MODEL_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
_MODEL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "models"
_MODEL_PATH = _MODEL_DIR / "lid.176.ftz"


def _load_model():
    """Download (if needed) and load the FastText language ID model."""
    global _model
    if _model is not None:
        return _model

    try:
        import fasttext
    except ImportError:
        # Silently fail to avoid overhead, fallback will be used
        return None

    # Download model if not present
    if not _MODEL_PATH.exists():
        logger.info(f"Downloading FastText language model to {_MODEL_PATH}...")
        os.makedirs(_MODEL_DIR, exist_ok=True)
        try:
            urllib.request.urlretrieve(_MODEL_URL, str(_MODEL_PATH))
            logger.info("FastText model downloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to download FastText model: {e}")
            return None

    # Load model (suppress FastText's own warnings about deprecated API)
    try:
        fasttext.FastText.eprint = lambda *args, **kwargs: None
        _model = fasttext.load_model(str(_MODEL_PATH))
        logger.info("FastText language model loaded.")
        return _model
    except Exception as e:
        logger.error(f"Failed to load FastText model: {e}")
        return None


def detect_language(text: str) -> Literal["en", "hi", "bn"]:
    """
    Detect whether `text` is English, Hindi, or Bengali.

    Returns one of: "en", "hi", "bn"

    Strategy:
    1. If text contains Bengali script (Unicode block 0x0980-0x09FF) → "bn"
    2. If text contains Devanagari script (Unicode block 0x0900-0x097F) → "hi"
    3. For romanized text (Hinglish / Banglish), use FastText model
    4. Default: "en"
    """
    if not text or not text.strip():
        return "en"

    # Quick script-based detection for native scripts (faster than model)
    has_bengali = any("\u0980" <= c <= "\u09FF" for c in text)
    has_devanagari = any("\u0900" <= c <= "\u097F" for c in text)

    if has_bengali:
        return "bn"
    if has_devanagari:
        return "hi"

    # For romanized text, use FastText
    model = _load_model()
    if model is None:
        # Fallback: Detect Hinglish/Banglish based on common stop words in Roman letters
        text_lower = text.lower()
        # Bengali Romanized (Banglish) markers — avoid very short/ambiguous words like "ki", "r", "a"
        bangla_roman_words = [
            "ami", "tumi", "amader", "kotha", "bolte", "ache", "bhul",
            "korte", "hobe", "thik", "bolche", "bhalo", "kothay", "ekhane",
            "kachhe", "apnar", "jabe", "asbe", "dite", "nite", "niye",
            "kemon", "dekho", "bole", "jano", "janao", "janio", "shunun",
        ]
        # Hindi Romanized (Hinglish) markers — distinct from Bengali
        hindi_roman_words = [
            "hai", "hain", "toh", "bhi", "kya", "kaise", "sakte", "hoon",
            "aap", "aur", "main", "suno", "batao", "chahiye", "milega",
            "kitna", "kitne", "kaisa", "kaisi", "wahan", "yahan", "unka",
            "mujhe", "tumhe", "humara", "tumhara", "theek", "nahin", "nahi",
        ]
        
        # Count matches (whole word only)
        bn_count = sum(1 for w in bangla_roman_words if re.search(rf"\b{re.escape(w)}\b", text_lower))
        hi_count = sum(1 for w in hindi_roman_words if re.search(rf"\b{re.escape(w)}\b", text_lower))
        
        if bn_count > 0 and bn_count >= hi_count:
            return "bn"
        elif hi_count > 0:
            return "hi"
            
        return "en"

    try:
        # FastText expects single-line input, no newlines
        clean_text = text.replace("\n", " ").strip()
        predictions = model.predict(clean_text, k=3)  # top 3 predictions
        labels, scores = predictions

        # FastText labels look like "__label__en", "__label__hi", etc.
        lang_map = {}
        for label, score in zip(labels, scores):
            lang_code = label.replace("__label__", "")
            lang_map[lang_code] = score

        # Check for our supported languages in order of priority
        hi_score = lang_map.get("hi", 0.0)
        bn_score = lang_map.get("bn", 0.0)
        en_score = lang_map.get("en", 0.0)

        # If Hindi or Bengali has a reasonable score, prefer it
        # (since the default is English, we give a slight bias to detect Indian languages)
        if hi_score > 0.3:
            return "hi"
        if bn_score > 0.3:
            return "bn"

        return "en"

    except Exception as e:
        logger.error(f"FastText prediction failed: {e}")
        return "en"


def detect_language_bcp47(text: str) -> str:
    """
    Same as detect_language() but returns BCP-47 locale codes
    used by Sarvam AI: "en-IN", "hi-IN", "bn-IN"
    """
    lang = detect_language(text)
    return {"en": "en-IN", "hi": "hi-IN", "bn": "bn-IN"}[lang]
