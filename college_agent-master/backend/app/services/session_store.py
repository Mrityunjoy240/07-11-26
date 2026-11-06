"""SQLite-backed session memory for the voice agent.

The in-memory ``GroqService._sessions`` / ``_session_langs`` dicts clear on
every server restart, which makes a returning caller a stranger ("aaj raat
baad wala abhi kya bola tha?"). This module persists every turn and the
session language, and rehydrates them at startup — so context survives
restarts, deployments, and crashes.

Tables (same DB as conversations):
    agent_session_meta(session_id, lang, updated_at)
    agent_session_turns(id, session_id, role, content, created_at)
"""

import logging
import json
import sqlite3
import time

from app.config import settings

logger = logging.getLogger(__name__)

_DB_PATH = None
_TURNS_KEPT = 12  # must match GroqService in-memory trimming


def _db() -> sqlite3.Connection:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = f"{settings.db_dir}/conversations.db"
    os = __import__("os")
    os.makedirs(settings.db_dir, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_session_meta (
            session_id TEXT PRIMARY KEY,
            lang TEXT NOT NULL DEFAULT 'en',
            default_lang TEXT,
            profile TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_session_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_turns_session ON agent_session_turns(session_id, id)"
    )
    # Migration for DBs created before default_lang/profile columns existed.
    for col in ("default_lang", "profile"):
        try:
            conn.execute(f"ALTER TABLE agent_session_meta ADD COLUMN {col} TEXT")
        except Exception:  # noqa: BLE001 — column already exists
            pass
    conn.commit()


def save_turn(
    session_id: str,
    user_msg: str,
    assistant_msg: str,
    lang: str,
    default_lang: str | None = None,
    profile: str | None = None,
) -> None:
    """Persist one user+assistant turn and the session language (best-effort)."""
    if not session_id or session_id == "default":
        return
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = _db()
        conn.execute(
            "INSERT INTO agent_session_turns (session_id, role, content, created_at) "
            "VALUES (?, 'user', ?, ?)",
            (session_id, (user_msg or "")[:2000], now),
        )
        conn.execute(
            "INSERT INTO agent_session_turns (session_id, role, content, created_at) "
            "VALUES (?, 'assistant', ?, ?)",
            (session_id, (assistant_msg or "")[:2000], now),
        )
        conn.execute(
            "INSERT INTO agent_session_meta (session_id, lang, default_lang, profile, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET lang = excluded.lang, "
            "default_lang = COALESCE(excluded.default_lang, agent_session_meta.default_lang), "
            "profile = COALESCE(excluded.profile, agent_session_meta.profile), "
            "updated_at = excluded.updated_at",
            (session_id, lang or "en", default_lang, profile, now),
        )
        conn.commit()
        conn.close()
    except Exception as e:  # noqa: BLE001 — persistence must never break the chat
        logger.warning(f"[SESSION_STORE] save failed for {session_id}: {e}")


def load_recent(max_sessions: int = 50, max_turns: int = _TURNS_KEPT, max_age_hours: int = 24):
    """Load recently active sessions for rehydration.

    Returns {session_id: {"turns": [{"role", "content"}, ...], "lang": str,
    "default_lang": str | None, "profile": dict | None}}
    with the last ``max_turns`` messages per session, newest-first session order.
    """
    cutoff = time.strftime(
        "%Y-%m-%d %H:%M:%S", time.localtime(time.time() - max_age_hours * 3600)
    )
    try:
        conn = _db()
        meta = conn.execute(
            "SELECT session_id, lang, default_lang, profile FROM agent_session_meta "
            "WHERE updated_at >= ? ORDER BY updated_at DESC LIMIT ?",
            (cutoff, max_sessions),
        ).fetchall()
        result: dict = {}
        for row in meta:
            sid = row["session_id"]
            turns = conn.execute(
                "SELECT role, content FROM agent_session_turns "
                "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (sid, max_turns),
            ).fetchall()
            result[sid] = {
                "turns": [
                    {"role": t["role"], "content": t["content"]}
                    for t in reversed(turns)
                ],
                "lang": row["lang"] or "en",
                "default_lang": row["default_lang"] or None,
                "profile": json.loads(row["profile"]) if row["profile"] else None,
            }
        conn.close()
        return result
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[SESSION_STORE] load failed: {e}")
        return {}


def delete_session(session_id: str) -> None:
    """Remove a session's persisted memory (privacy / end-of-call)."""
    try:
        conn = _db()
        conn.execute("DELETE FROM agent_session_turns WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM agent_session_meta WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[SESSION_STORE] delete failed for {session_id}: {e}")
