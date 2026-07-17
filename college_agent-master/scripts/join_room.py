"""
Join a specific LiveKit session by dispatching the bcrec-agent to it.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv("backend/.env", override=True)
sys.path.insert(0, os.path.abspath("backend"))

from livekit import api


async def join_room(room_name: str):
    lkapi = api.LiveKitAPI(
        url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET"),
    )

    # Check if room exists
    rooms = await lkapi.room.list_rooms(api.ListRoomsRequest())
    existing = [r.name for r in rooms.rooms]
    print(f"Existing sessions: {existing}")

    if room_name not in existing:
        print(f"Session '{room_name}' doesn't exist. Creating it...")
        await lkapi.room.create_room(api.CreateRoomRequest(name=room_name))
        print(f"Session '{room_name}' created.")
    else:
        print(f"Session '{room_name}' already exists.")

    # Dispatch the agent to the session
    await lkapi.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            agent_name="bcrec-agent",
            room=room_name,
        )
    )
    print(f"Agent 'bcrec-agent' dispatched to session '{room_name}'.")

    await asyncio.sleep(2)

    # Check dispatch status
    dispatches = await lkapi.agent_dispatch.list_dispatch(room_name)
    for d in dispatches:
        print(f"  Dispatch {d.id}: state={d.state}")

    await lkapi.aclose()


if __name__ == "__main__":
    room = sys.argv[1] if len(sys.argv) > 1 else "console-a338c582"
    asyncio.run(join_room(room))
