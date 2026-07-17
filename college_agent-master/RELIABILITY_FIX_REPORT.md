# Reliability Fix Report — v0.9.0-pre-security

## Fixes Applied

---

### B8: DemoLogger Unbounded Memory Growth

**Root Cause**: `app/services/llm/safe_point.py:139-150`

`DemoLogger` used a plain Python `list` to accumulate log entries. Every call
to `log()` appended a new dict, and `flush()` only *read* entries without ever
removing them. Over time the list grew without bound, consuming all available
memory under sustained traffic.

**Retention Strategy**: Bounded deque with maxlen=1000.

- A `collections.deque(maxlen=1000)` replaces the plain list.
- When the deque reaches 1000 entries, the oldest entry is automatically
  discarded on each new append — constant memory footprint.
- 1000 entries at ~200 bytes each ≈ 200 KB worst case.
- `flush()` still works unchanged; `deque` supports all the iteration and
  comprehension operations that `flush()` uses.

**Fix** (`app/services/llm/safe_point.py`):

```python
# Before:
class DemoLogger:
    def __init__(self):
        self.logs: list[dict] = []

# After:
class DemoLogger:
    MAX_LOG_ENTRIES = 1000
    def __init__(self):
        self.logs: deque = deque(maxlen=self.MAX_LOG_ENTRIES)
```

Also added `from collections import deque` at the top of the file.

**Behavior preserved**: `log()` still appends, `logger.info()` still fires on
every entry, `flush(session_id)` still filters and reports relevant entries.
No caller observes any API difference — `deque` supports `len()`, indexing,
iteration, and list comprehension identically to `list`.

**Regression Risk**: None. `deque` is a strict superset of list for the
operations used. The only semantic difference is the automatic eviction of
old entries at capacity — which is the desired fix.

---

### B2: SQLite Concurrent Write Collisions

**Root Cause**: `app/database.py:14-17`

`get_db()` opened connections with `check_same_thread=False` (allowing use
from multiple threads) and enabled WAL mode (good for concurrent *reads*),
but did not set `PRAGMA busy_timeout`. When two threads or async tasks
attempted simultaneous writes, one would immediately fail with:
`sqlite3.OperationalError: database is locked`

**Fix**: Added `PRAGMA busy_timeout = 5000` (5 second retry on write locks).

```python
# Before:
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

# After:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn
```

**How it works**: SQLite's `busy_timeout` tells the database engine to retry
a write operation for up to N milliseconds when another connection holds the
write lock. With WAL mode + 5s timeout:
- Multiple *readers* proceed concurrently (WAL)
- Multiple *writers* serialize with automatic retry (busy_timeout)
- No connection is lost — the worst case is a 5s latency spike under write
  contention, not a crash

**Not changed**: `check_same_thread=False` must remain (async routes call
`get_db()` from different threads). SQLite remains the database (per
requirements). No Redis/Postgres introduced.

**Regression Risk**: None. `busy_timeout` only changes what happens *during*
a write lock — it turns a crash into a retry. No behavioral change when
there is no contention.

---

## Stress Test Results

```
RELIABILITY FIX STRESS TESTS
  11 passed, 0 failed out of 11

  PASS  logs is deque                        (B8: type)
  PASS  maxlen is 1000                       (B8: capacity)
  PASS  logs capped at maxlen                (B8: bounded growth)
  PASS  oldest entry > 100                   (B8: eviction works)
  PASS  flush completes without error        (B8: flush preserved)
  PASS  append after cap works               (B8: new entries accepted)
  PASS  newest entry present                 (B8: newest preserved)
  PASS  busy_timeout is 5000                 (B2: pragma set)
  PASS  concurrent writes succeed            (B2: 20 concurrent ops)
  PASS  QA returns 200                       (regression: QA works)
  PASS  QA has answer                        (regression: answer intact)
```

The concurrent write test launched 20 database mutations (conversation
creation + message addition) from a 10-thread pool. All succeeded. No
`database is locked` errors.

---

## Files Changed

| File | Change |
|------|--------|
| `app/services/llm/safe_point.py:1` | Added `from collections import deque` |
| `app/services/llm/safe_point.py:139-141` | Changed `list` → `deque(maxlen=1000)` |
| `app/database.py:17` | Added `PRAGMA busy_timeout = 5000` |

---

*Generated: 2026-07-11*
