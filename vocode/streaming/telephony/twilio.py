import os
from typing import Optional
from dotenv import load_dotenv
from twilio.rest import Client

from vocode.streaming.models.telephony import TwilioConfig

load_dotenv()


def create_twilio_client(twilio_config: TwilioConfig):
    return Client(twilio_config.account_sid, twilio_config.auth_token)
