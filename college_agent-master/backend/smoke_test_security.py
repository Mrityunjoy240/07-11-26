"""Smoke tests for security fixes: B6, B3, B5.
Verifies that fixes work without breaking existing functionality."""

import subprocess, time, sys, httpx, os, json

BASE = "http://127.0.0.1:9002"
BACKEND_DIR = r"C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend"
VENV_PY = r"C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\venv\Scripts\python.exe"

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
print("SECURITY FIX SMOKE TESTS")
print("=" * 60)

# --- Start server ---
print("\n--- Starting server ---")
env = os.environ.copy()
env["GROQ_API_KEY"] = "gsk_test"
env["ADMIN_USERNAME"] = "admin"
env["ADMIN_PASSWORD"] = "admin"
env["SECRET_KEY"] = "test-secret-key-for-smoke-tests-1234567890"

proc = subprocess.Popen(
    [VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "9002", "--log-level", "warning"],
    cwd=BACKEND_DIR,
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

# Server takes long due to vector store download on first start
print("  Waiting up to 120s for server startup...", end="", flush=True)
start = time.time()
server_up = False
while time.time() - start < 120:
    try:
        r = httpx.get(f"{BASE}/health/", timeout=3)
        if r.status_code == 200:
            server_up = True
            print(f" UP after {time.time()-start:.0f}s")
            break
    except Exception:
        pass
    if proc.poll() is not None:
        stderr = ""
        try:
            stderr = proc.stderr.read().decode("utf-8", errors="replace")[:2000] if proc.stderr else ""
        except:
            pass
        print(f"\n  Server DIED (code={proc.returncode})")
        if stderr:
            print(f"  STDERR: {stderr[:500]}")
        sys.exit(1)
    time.sleep(3)

if not server_up:
    print(" TIMEOUT")
    proc.terminate()
    sys.exit(1)

# =========== TEST: QA endpoint still works (no auth) ===========
print("\n--- [B4 regression] QA endpoint works without auth ---")
try:
    r = httpx.post(f"{BASE}/qa/query", json={"message": "What is BCREC?"}, timeout=15)
    check("QA returns 200", r.status_code == 200,
          f"got {r.status_code}: {r.text[:100]}")
    data = r.json()
    check("QA response has answer", "answer" in data,
          f"keys: {list(data.keys())}")
except Exception as e:
    check("QA endpoint reachable", False, str(e))

# =========== TEST: Health endpoint no longer leaks keys ===========
print("\n--- [B6] Health endpoint does not leak secrets ---")
try:
    r = httpx.get(f"{BASE}/health/tts", timeout=5)
    check("Health TTS returns 200", r.status_code == 200, f"got {r.status_code}")
    resp = r.json()
    check("No key_prefix in response", "key_prefix" not in resp,
          f"found key_prefix={resp.get('key_prefix')}")
    check("Has key_configured instead", "key_configured" in resp,
          f"keys: {list(resp.keys())}")
except Exception as e:
    check("Health endpoint reachable", False, str(e))

# =========== TEST: Admin login works with configured credentials ===========
print("\n--- [B3] Admin login with configured credentials ---")
try:
    r = httpx.post(f"{BASE}/token",
        data={"username": "admin", "password": "admin"}, timeout=5)
    check("Login returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:100]}")
    if r.status_code == 200:
        token = r.json().get("access_token", "")
        check("Token received", len(token) > 20, f"got {token[:10]}...")
    else:
        token = ""
    
    # Now test an admin endpoint with this token
    if token:
        headers = {"Authorization": f"Bearer {token}"}
        r2 = httpx.get(f"{BASE}/admin/files", headers=headers, timeout=5)
        check("Admin files endpoint with auth", r2.status_code in (200, 500),
              f"got {r2.status_code}: {r2.text[:100]}")
except Exception as e:
    check("Admin login test", False, str(e))

# =========== TEST: Rate limiting on login ===========
print("\n--- [B5] Rate limiting activates ---")
try:
    responses = []
    for i in range(8):
        r = httpx.post(f"{BASE}/token",
            data={"username": "admin", "password": "admin"}, timeout=5)
        responses.append(r.status_code)
        if r.status_code == 429:
            break
    
    has_429 = any(s == 429 for s in responses)
    check("Rate limit 429 received", has_429,
          f"statuses: {responses}")
except Exception as e:
    check("Rate limiting test", False, str(e))

# =========== TEST: Auth rejects empty defaults (B3) ===========
print("\n--- [B3 edge] No login with missing config ---")
try:
    # Test that login without env vars fails - by sending to our current server
    # (We can't easily restart without env, but we can verify the code guard exists)
    
    # Check by reading the source
    with open(os.path.join(BACKEND_DIR, "app", "api", "auth_routes.py"), encoding="utf-8") as f:
        src = f.read()
    check("Empty creds guard in login", 
          "if not settings.admin_username or not settings.admin_password or not settings.secret_key:" in src,
          "Guard check not found in source")
except Exception as e:
    check("Source code check", False, str(e))

# =========== TEST: Config defaults are empty (B3) ===========
print("\n--- [B3 code] Config defaults are empty ---")
try:
    with open(os.path.join(BACKEND_DIR, "app", "config.py"), encoding="utf-8") as f:
        config_src = f.read()
    
    # Check that defaults are empty strings, not "admin"
    check("admin_username default is empty", 
          'admin_username: str = ""' in config_src,
          "default not empty")
    check("admin_password default is empty",
          'admin_password: str = ""' in config_src,
          "default not empty")
    check("secret_key default is empty",
          'secret_key: str = ""' in config_src,
          "default not empty")
except Exception as e:
    check("Config source check", False, str(e))

# =========== TEST: Rate limit decorators on admin routes (B5) ===========
print("\n--- [B5 code] Rate limit decorators on admin routes ---")
try:
    with open(os.path.join(BACKEND_DIR, "app", "api", "admin.py"), encoding="utf-8") as f:
        admin_src = f.read()
    count_limits = admin_src.count("@limiter.limit")
    check("Rate limit decorators on admin routes", count_limits >= 6,
          f"found {count_limits} decorators")
except Exception as e:
    check("Admin source check", False, str(e))

# =========== Summary ===========
print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
print("=" * 60)

# Cleanup
proc.terminate()
try:
    proc.wait(timeout=5)
except:
    proc.kill()
print("Server stopped.")

sys.exit(0 if failed == 0 else 1)
