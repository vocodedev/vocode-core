from typing import Optional
import vonage
from twilio.rest import Client

from vocode.streaming.models.telephony import TwilioConfig, VonageConfig


def create_twilio_client(twilio_config: TwilioConfig):
    twilio_client = Client(twilio_config.account_sid, twilio_config.auth_token)
    try:
        # Test credentials
        twilio_client.api.accounts(twilio_config.account_sid).fetch()
        return twilio_client
    except Exception as e:
        raise RuntimeError("Could not create Twilio client. Invalid credentials") from e

def create_vonage_client(vonage_config: VonageConfig):
    client = vonage.Client(
        key=vonage_config.api_key,
        secret=vonage_config.api_secret,
        application_id=vonage_config.application_id,
        private_key=vonage_config.private_key,
    )
    voice = vonage.Voice(client)
    return voice

def end_twilio_call(twilio_client: Client, twilio_sid: str) -> bool:
    response = twilio_client.calls(twilio_sid).update(status="completed")
    return response.status == "completed"

def end_vonage_call(vonage_client: Client, vonage_uuid: str) -> bool:
    response = vonage_client.update_call(uuid=vonage_uuid, action="hangup")
    return True