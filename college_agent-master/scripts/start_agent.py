"""Start agent worker and dispatch to LiveKit room."""

import subprocess
import sys
import os
import time
import asyncio

# 1. Start the agent worker with logging to file
logfile = open("agent_log.txt", "w", encoding="utf-8")
proc = subprocess.Popen(
    [sys.executable, "scripts/livekit_agent.py", "start"],
    stdout=logfile,
    stderr=subprocess.STDOUT,
    env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP")
    else 0,
)
print(f"Agent PID: {proc.pid}")

# 2. Wait for it to register
import sys

sys.path.insert(0, "backend")
from dotenv import load_dotenv

load_dotenv("backend/.env", override=True)

from livekit.api import LiveKitAPI
from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest


async def dispatch():
    api = LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )
    req = CreateAgentDispatchRequest(agent_name="bcrec-agent", room="console-f7d1f37e")
    result = await api.agent_dispatch.create_dispatch(req)
    print(f"Dispatch: {result}")
    await api.aclose()


asyncio.run(dispatch())
print(f"Agent running PID {proc.pid}. Check agent_log.txt for output.")
print(f"Stop with: taskkill /F /PID {proc.pid}")
