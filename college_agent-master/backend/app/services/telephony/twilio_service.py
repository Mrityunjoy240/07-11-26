import logging

from twilio.rest import Client

from app.config import settings

logger = logging.getLogger(__name__)


class TwilioService:
    def __init__(self):
        self.account_sid = settings.twilio_account_sid
        self.auth_token = settings.twilio_auth_token
        self.from_number = settings.twilio_phone_number
        self.client = None

        if self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio Client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio Client: {e}")

    def make_outbound_call(self, to_number: str, webhook_url: str):
        """
        Initiate an outbound call to a specific number.
        The webhook_url should point to an endpoint that returns TwiML.
        """
        if not self.client:
            logger.error("Twilio Client not initialized")
            return {"success": False, "error": "Twilio Client not initialized"}

        try:
            call = self.client.calls.create(to=to_number, from_=self.from_number, url=webhook_url)
            logger.info(f"Outbound call initiated: {call.sid} to {to_number}")
            return {"success": True, "call_sid": call.sid}
        except Exception as e:
            logger.error(f"Failed to initiate outbound call: {e}")
            return {"success": False, "error": str(e)}


_twilio_service = None


def get_twilio_service() -> TwilioService:
    global _twilio_service
    if _twilio_service is None:
        _twilio_service = TwilioService()
    return _twilio_service
