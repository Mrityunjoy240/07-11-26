import logging

from app.config import settings

logger = logging.getLogger(__name__)

try:
    from livekit import api

    LIVEKIT_AVAILABLE = True
except ImportError:
    LIVEKIT_AVAILABLE = False
    logger.warning("livekit-server-sdk not installed. LiveKit service will be limited.")


class LiveKitService:
    """
    LiveKit Service for real-time audio transport.
    Handles token generation and room management.
    """

    def __init__(self, url: str, api_key: str, api_secret: str):
        self.url = url
        self.api_key = api_key
        self.api_secret = api_secret

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_secret and self.url)

    def generate_token(self, room_name: str, participant_identity: str) -> str:
        """
        Generate a token for a participant to join a room.
        """
        if not LIVEKIT_AVAILABLE:
            logger.error("LiveKit SDK not available")
            return ""

        try:
            token = (
                api.AccessToken(self.api_key, self.api_secret)
                .with_identity(participant_identity)
                .with_name(participant_identity)
                .with_grants(
                    api.VideoGrants(
                        room_join=True,
                        room=room_name,
                        can_publish=True,
                        can_subscribe=True,
                    )
                )
            )

            return token.to_jwt()
        except Exception as e:
            logger.error(f"Failed to generate LiveKit token: {e}")
            return ""


# Global instance
_livekit_service = None


def get_livekit_service() -> LiveKitService:
    global _livekit_service
    if _livekit_service is None:
        _livekit_service = LiveKitService(
            url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
    return _livekit_service
