from typing import Optional
from twilio.rest import Client

from vocode.streaming.models.telephony import TwilioConfig


def create_twilio_client(twilio_config: TwilioConfig):
    return Client(twilio_config.account_sid, twilio_config.auth_token)
