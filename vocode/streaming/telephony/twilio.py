from typing import Optional
from twilio.rest import Client

from vocode.streaming.models.telephony import TwilioConfig


def create_twilio_client(twilio_config: TwilioConfig):
    return Client(twilio_config.account_sid, twilio_config.auth_token)


def end_twilio_call(twilio_client: Client, twilio_sid: str) -> bool:
    response = twilio_client.calls(twilio_sid).update(status="completed")
    return response.status == "completed"
