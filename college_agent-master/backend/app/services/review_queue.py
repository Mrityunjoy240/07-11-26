"""Staff review queue — the "training loop" for non-technical college staff.

Every fallback / low-confidence / "didn't understand" response is captured
here with the original query, so staff can see what the bot failed on, write
the correct answer into the knowledge base, and re-index — improving the bot
without touching code.

Storage: SQLite (same DB as conversations), table ``review_queue``.
"""

import logging
import sqlite3
import time
import uuid

from app.config import settings

logger = logging.getLogger(__name__)

DB_PATH = None  # resolved lazily to avoid import-time settings issues

# Sources that mean "the bot did not really answer" and deserve staff eyes.
_FALLBACK_SOURCES = (
    "transcript_clarification",
    "transcript_noise",
    "safe_point_bengali",
    "safe_point_unknown",
    "grounded_refusal",
    "clarification",
)

# Known fallback answer strings (kept in sync with safe_point.py).
_FALLBACK_ANSWERS = {
    "আমি পুরোটা বুঝতে পারিনি। আরেকবার একটু ধীরে বলবেন?",
    "I am not completely sure about that information, "
    "but I can connect you with the admission office. "
    "Please call 0343-2501353.",
    "I am sorry for the delay. Let me help using the information I already have.",
}

_CONFIDENCE_THRESHOLD = 0.5


def _db() -> sqlite3.Connection:
    global DB_PATH
    if DB_PATH is None:
        DB_PATH = settings.db_dir + "/conversations.db"
    os = __import__("os")
    os.makedirs(settings.db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    _ensure_table(conn)
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS review_queue (
            id TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            session_id TEXT NOT NULL,
            query TEXT NOT NULL,
            answer TEXT NOT NULL,
            source TEXT NOT NULL,
            confidence REAL,
            status TEXT NOT NULL DEFAULT 'open',
            staff_note TEXT DEFAULT ''
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_review_status ON review_queue(status)"
    )
    conn.commit()


def _needs_review(result: dict) -> bool:
    """Language/design-agnostic heuristic: did this response actually answer?"""
    source = (result.get("source") or "").lower()
    if source == "safe_point_handoff":
        return False
    if any(source.startswith(prefix) or prefix in source for prefix in _FALLBACK_SOURCES):
        return True
    answer = (result.get("answer") or "").strip()
    if answer in _FALLBACK_ANSWERS:
        return True
    try:
        if result.get("confidence") is not None and float(result["confidence"]) < _CONFIDENCE_THRESHOLD:
            return True
    except (TypeError, ValueError):
        pass
    return False


def capture(session_id: str, query: str, result: dict) -> None:
    """Record a weak response into the staff review queue (best-effort)."""
    if not result or not result.get("answer"):
        return
    if not _needs_review(result):
        return
    try:
        conn = _db()
        conn.execute(
            """
            INSERT OR REPLACE INTO review_queue
                (id, ts, session_id, query, answer, source, confidence, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'open')
            """,
            (
                str(uuid.uuid4()),
                time.strftime("%Y-%m-%d %H:%M:%S"),
                session_id,
                (query or "")[:500],
                (result.get("answer") or "")[:2000],
                (result.get("source") or "?")[:100],
                result.get("confidence"),
            ),
        )
        conn.commit()
        conn.close()
        logger.info(
            f"[REVIEW_QUEUE] captured session={session_id} "
            f"source={result.get('source')} query='{query[:60]}'"
        )
    except Exception as e:  # noqa: BLE001 — capture must never break the chat
        logger.warning(f"[REVIEW_QUEUE] capture failed: {e}")


def list_open(limit: int = 100) -> list[dict]:
    try:
        conn = _db()
        rows = conn.execute(
            "SELECT id, ts, session_id, query, answer, source, confidence, status, staff_note "
            "FROM review_queue WHERE status = 'open' ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[REVIEW_QUEUE] list failed: {e}")
        return []


def resolve(item_id: str, note: str = "") -> bool:
    """Mark a queue item as handled by staff (optionally with a note)."""
    try:
        conn = _db()
        cur = conn.execute(
            "UPDATE review_queue SET status = 'answered', staff_note = ? WHERE id = ?",
            (note or "", item_id),
        )
        conn.commit()
        conn.close()
        return cur.rowcount > 0
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[REVIEW_QUEUE] resolve failed: {e}")
        return False
