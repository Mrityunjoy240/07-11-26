import subprocess, sys, os, time, asyncio, socket

# Free port 8081 if in use
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(("127.0.0.1", 8081))
    s.close()
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
    for line in out.stdout.splitlines():
        if "8081" in line and "LISTENING" in line:
            pid = line.strip().split()[-1]
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
            print(f"Killed PID {pid} on port 8081")
            time.sleep(1)
            break
except:
    s.close()

log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, "agent.log")

proc = subprocess.Popen(
    [sys.executable, "scripts/livekit_agent.py", "start"],
    stdout=open(log_path, "w", encoding="utf-8"),
    stderr=subprocess.STDOUT,
    env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
)
print(f"Agent PID: {proc.pid}")
print(f"Log: {log_path}")

# Wait for prewarm
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from dotenv import load_dotenv

load_dotenv("backend/.env", override=True)

time.sleep(20)

with open(log_path) as f:
    content = f.read()
    if "Prewarm complete" in content:
        print("Prewarm complete - agent ready")
    else:
        lines = content.strip().split("\n")
        for l in lines[-5:]:
            print(f"  {l}")

from livekit.api import LiveKitAPI
from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest


async def go():
    api = LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )
    r = await api.agent_dispatch.create_dispatch(
        CreateAgentDispatchRequest(agent_name="bcrec-agent", room="console-f7d1f37e")
    )
    print(f"Dispatched: {r.id} to {r.room}")
    await api.aclose()


asyncio.run(go())
print(f"Agent PID {proc.pid} running. Stop: taskkill /F /PID {proc.pid}")
