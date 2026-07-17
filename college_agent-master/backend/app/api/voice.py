import asyncio
import base64
import json
import logging
import uuid

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Response,
    WebSocket,
)
from pydantic import BaseModel

try:
    import audioop
except ImportError:
    import audioop_lts as audioop
from livekit import api, rtc

from app.services.livekit_session import get_livekit_service
from app.services.telephony.twilio_service import get_twilio_service

logger = logging.getLogger(__name__)
router = APIRouter()


class TokenRequest(BaseModel):
    room_name: str
    participant_identity: str | None = None


class OutboundCallRequest(BaseModel):
    phone_number: str
    base_url: str


@router.post("/token")
async def get_token(request: TokenRequest):
    lk = get_livekit_service()
    if not lk.is_available():
        raise HTTPException(status_code=503, detail="LiveKit service not configured")

    identity = request.participant_identity or f"user_{uuid.uuid4().hex[:8]}"
    token = lk.generate_token(request.room_name, identity)

    if not token:
        raise HTTPException(status_code=500, detail="Failed to generate token")

    return {"token": token, "identity": identity, "server_url": lk.url}


@router.post("/call-me")
async def call_me(request: OutboundCallRequest):
    twilio = get_twilio_service()
    # Pass phone number in query param to the webhook
    from urllib.parse import quote

    webhook_url = f"{request.base_url}/voice/twiml/outbound?phone={quote(request.phone_number)}"

    result = twilio.make_outbound_call(request.phone_number, webhook_url)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.post("/twiml/outbound")
async def twiml_outbound(request: Request):
    from urllib.parse import quote
    phone_number = request.query_params.get("phone", "unknown")
    try:
        host = request.headers.get("host")
        if not host:
            raise ValueError("Host header is missing")
        proto = "wss" if request.url.scheme == "https" else "ws"
        stream_url = f"{proto}://{host}/voice/stream?phone={quote(phone_number)}"
    except Exception as e:
        logger.error(f"Error constructing stream URL: {e}")
        raise HTTPException(status_code=500, detail="Could not determine stream URL")

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}" />
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@router.websocket("/stream")
async def twilio_stream(websocket: WebSocket):
    await websocket.accept()
    phone_number = websocket.query_params.get("phone", "unknown")
    logger.info(f"Twilio Media Stream connected for: {phone_number}")

    from app.config import settings

    room_name = f"call_{uuid.uuid4().hex[:10]}"
    participant_identity = f"twilio_{uuid.uuid4().hex[:6]}"

    # Attach phone number to metadata so Agent can read it
    metadata = json.dumps({"phone_number": phone_number})

    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(participant_identity)
        .with_metadata(metadata)
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )

    room = rtc.Room()
    source = rtc.AudioSource(16000, 1)
    track = rtc.LocalAudioTrack.create_audio_track("twilio-voice", source)
    stream_sid = None
    resample_state = None

    @room.on("track_subscribed")
    def on_track_subscribed(
        track_remote: rtc.RemoteAudioTrack,
        publication: rtc.RemoteTrackPublication,
        participant_remote: rtc.RemoteParticipant,
    ):
        async def forward_audio():
            try:
                stream = rtc.AudioStream(track_remote, sample_rate=8000, num_channels=1)
                audio_buffer = b""
                async for event in stream:
                    if not stream_sid:
                        continue
                    try:
                        audio_buffer += bytes(event.frame.data)
                        while len(audio_buffer) >= 320:
                            payload_to_send = audio_buffer[:320]
                            audio_buffer = audio_buffer[320:]
                            ulaw_data = audioop.lin2ulaw(payload_to_send, 2)
                            # Log every 50 packets to avoid flooding
                            if not hasattr(websocket, "packet_count"):
                                websocket.packet_count = 0
                            websocket.packet_count += 1
                            if websocket.packet_count % 50 == 0:
                                logger.info(
                                    f"Bridge sending audio packet {websocket.packet_count} to Twilio"
                                )

                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "event": "media",
                                        "streamSid": stream_sid,
                                        "media": {"payload": base64.b64encode(ulaw_data).decode()},
                                    }
                                )
                            )
                    except Exception:
                        pass
            except Exception:
                pass

        asyncio.create_task(forward_audio())

    try:
        await room.connect(settings.livekit_url, token)
        options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        await room.local_participant.publish_track(track, options)

        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)
            if data["event"] == "start":
                stream_sid = data["start"]["streamSid"]
            elif data["event"] == "media":
                payload = base64.b64decode(data["media"]["payload"])
                pcm_8k = audioop.ulaw2lin(payload, 2)
                # Resample to 16kHz for Agent VAD
                pcm_16k, resample_state = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, resample_state)
                await source.capture_frame(rtc.AudioFrame(pcm_16k, 16000, 1, len(pcm_16k) // 2))
            elif data["event"] == "stop":
                break
    except Exception as e:
        logger.error(f"Bridge Error: {e}")
    finally:
        if room.isconnected():
            await room.disconnect()
