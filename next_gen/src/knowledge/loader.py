"""Knowledge base loader — reads JSON files and provides access."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_KB_PATH = _DATA_DIR / "knowledge_base.json"


class KnowledgeBase:
    """Loads and provides access to the college knowledge base."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if self._loaded:
            return
        self._data: dict[str, Any] = {}
        self._load()
        self._loaded = True

    def _load(self):
        """Load knowledge base from JSON file."""
        if not _KB_PATH.exists():
            logger.error(f"Knowledge base not found at {_KB_PATH}")
            return

        try:
            with open(_KB_PATH, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            logger.info(f"Loaded knowledge base ({os.path.getsize(_KB_PATH)} bytes)")
        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a top-level value from the knowledge base."""
        if isinstance(self._data, dict) and key in self._data:
            return self._data[key]
        return default

    def get_department(self, code: str) -> dict[str, Any]:
        """Get department information by code."""
        depts = self.get("departments", default={})
        return depts.get(code.upper(), {})

    def get_all_departments(self) -> dict[str, Any]:
        """Get all departments."""
        return self.get("departments", default={})

    def search_department_code(self, query: str) -> str | None:
        """Extract department code from query text."""
        q = query.lower()
        dept_map = {
            "cse": "CSE", "computer": "CSE", "cs": "CSE",
            "it": "IT", "information": "IT",
            "ece": "ECE", "electronics": "ECE",
            "ee": "EE", "electrical": "EE",
            "me": "ME", "mechanical": "ME",
            "ce": "CE", "civil": "CE",
            "csd": "CSD", "design": "CSD",
            "aiml": "AIML", "ai": "AIML", "ai ml": "AIML",
            "ds": "DS", "data science": "DS",
            "cy": "CY", "cyber": "CY",
        }
        _ambig = frozenset({'it', 'me'})
        for alias in sorted(dept_map, key=len, reverse=True):
            if not re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", q):
                continue
            if alias in _ambig and alias.upper() not in query:
                continue
            return dept_map[alias]
        return None

    def reload(self):
        """Reload the knowledge base from disk."""
        self._loaded = False
        self._load()
        self._loaded = True


def get_kb() -> KnowledgeBase:
    """Get the singleton knowledge base instance."""
    return KnowledgeBase()
