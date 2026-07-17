import subprocess, time, sys, httpx, os

env = os.environ.copy()
env['GROQ_API_KEY'] = 'gsk_test'
proc = subprocess.Popen(
    [r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\venv\Scripts\python.exe',
     '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8001'],
    cwd=r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend',
    env=env,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)
print('Starting server...')
time.sleep(15)

try:
    # Test actual auth endpoint
    r = httpx.post('http://127.0.0.1:8001/token',
        data={'username': 'admin', 'password': 'admin'},
        timeout=5)
    print('POST /token:', r.status_code)
    if r.status_code == 200:
        token = r.json()['access_token']
        print('  Token received (first 20 chars):', token[:20])
    else:
        print('  Body:', r.text[:200])

    # Test with wrong password to confirm auth is working
    r2 = httpx.post('http://127.0.0.1:8001/token',
        data={'username': 'admin', 'password': 'wrong'},
        timeout=5)
    print('POST /token (wrong pw):', r2.status_code)
except Exception as e:
    print('Error:', e)
finally:
    proc.terminate()
    proc.wait()
    print('Server stopped')
