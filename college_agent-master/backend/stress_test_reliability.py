"""Stress tests for reliability fixes: B8 (DemoLogger) and B2 (SQLite)."""
import subprocess, time, sys, httpx, os, threading, concurrent.futures

BACKEND_DIR = r"C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend"
VENV_PY = r"C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\venv\Scripts\python.exe"
BASE = "http://127.0.0.1:9012"

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")

print("=" * 60)
print("RELIABILITY FIX STRESS TESTS")
print("=" * 60)

# =========== B8: DemoLogger bounded growth ===========
print("\n=== [B8] DemoLogger bounded memory ===")

import sys as _sys
_sys.path.insert(0, BACKEND_DIR)
os.environ["GROQ_API_KEY"] = "gsk_test"

from collections import deque as _deque
from app.services.llm.safe_point import DemoLogger

dl = DemoLogger()

# Verify type
check("logs is deque", isinstance(dl.logs, _deque),
      f"type is {type(dl.logs)}")
check("maxlen is 1000", dl.logs.maxlen == 1000,
      f"maxlen={dl.logs.maxlen}")

# Fill past capacity
for i in range(1100):
    dl.log(f"session_{i % 5}", {"event": "test", "session_id": f"session_{i % 5}", "i": i})

check("logs capped at maxlen", len(dl.logs) == 1000,
      f"len={len(dl.logs)}")

# Verify oldest entries were dropped
oldest_i = dl.logs[0].get("i", -1)
check("oldest entry > 100", oldest_i >= 100,
      f"oldest i={oldest_i}")

# Verify flush still works
dl.flush("session_0")
# flush should still report but not throw
check("flush completes without error", True)

# Verify new entries still appended after cap
dl.log("session_new", {"event": "post_fill", "session_id": "session_new"})
check("append after cap works", len(dl.logs) == 1000,
      f"len={len(dl.logs)}")
check("newest entry present", dl.logs[-1].get("event") == "post_fill",
      f"last event={dl.logs[-1].get('event')}")

print("\n=== [B2] SQLite concurrent writes ===")

# --- Start server ---
print("  Starting server...")
env = os.environ.copy()
env["GROQ_API_KEY"] = "gsk_test"
env["ADMIN_USERNAME"] = "admin"
env["ADMIN_PASSWORD"] = "admin"
env["SECRET_KEY"] = "test-secret-key-for-smoke"

proc = subprocess.Popen(
    [VENV_PY, "-m", "uvicorn", "app.main:app",
     "--host", "127.0.0.1", "--port", "9012", "--log-level", "warning"],
    cwd=BACKEND_DIR, env=env,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)

start = time.time()
server_up = False
while time.time() - start < 120:
    try:
        r = httpx.get(f"{BASE}/health/", timeout=3)
        if r.status_code == 200:
            server_up = True
            print(f"  Server UP after {time.time()-start:.0f}s")
            break
    except:
        pass
    if proc.poll() is not None:
        print("  Server DIED")
        sys.exit(1)
    time.sleep(3)

if not server_up:
    print("  Server TIMEOUT")
    sys.exit(1)

# Test PRAGMA busy_timeout is set
print("\n  --- db init with busy_timeout ---")
from app.database import get_db
conn = get_db()
cur = conn.execute("PRAGMA busy_timeout")
timeout_val = cur.fetchone()[0]
check("busy_timeout is 5000", timeout_val == 5000,
      f"got busy_timeout={timeout_val}")
conn.close()

# Concurrent write stress test
print("\n  --- 20 concurrent conversation creates + message adds ---")
import random as _random, string as _string

def create_and_write(_):
    """Create a conversation and add a message to it."""
    try:
        # Create conversation (no body needed, auto-generates)
        r = httpx.post(f"{BASE}/api/conversations", timeout=10)
        if r.status_code != 200:
            return ("create_fail", r.status_code)
        conv_id = r.json().get("id", "")

        # Add a message (this does a write)
        r2 = httpx.post(f"{BASE}/api/conversations/{conv_id}/messages",
            json={"role": "user", "content": f"Test message from concurrent write {_}"},
            timeout=10)
        return ("ok", r2.status_code) if r2.status_code < 400 else ("msg_fail", r2.status_code)
    except Exception as e:
        return ("error", str(e))

results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
    futures = [pool.submit(create_and_write, i) for i in range(20)]
    for f in concurrent.futures.as_completed(futures):
        results.append(f.result())

ok_count = len([r for r in results if r[0] == "ok"])
errors = [r for r in results if r[0] == "error"]
create_fails = [r for r in results if r[0] == "create_fail"]
msg_fails = [r for r in results if r[0] == "msg_fail"]

check("concurrent writes succeed", ok_count > 0,
      f"{ok_count} ok, {len(errors)} exceptions, {len(create_fails)} create fails, {len(msg_fails)} msg fails")
if msg_fails:
    print(f"    Message fail HTTP codes: {set(r[1] for r in msg_fails)}")
if errors:
    for e in errors[:3]:
        print(f"    Exception: {e[1][:150]}")

# QA still works (no regression)
print("\n  --- QA regression check ---")
try:
    r = httpx.post(f"{BASE}/qa/query", json={"message": "What is BCREC?"}, timeout=15)
    check("QA returns 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        check("QA has answer", "answer" in data, f"keys: {list(data.keys())}")
except Exception as e:
    check("QA endpoint", False, str(e))

# Summary
print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
print("=" * 60)

proc.terminate()
try:
    proc.wait(timeout=5)
except:
    proc.kill()
print("Server stopped.")

sys.exit(0 if failed == 0 else 1)
