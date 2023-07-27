from typing import Optional
from vocode.streaming.models.telephony import TwilioConfig, VonageConfig
from vocode.streaming.telephony.client.base_telephony_client import BaseTelephonyClient
from vocode.streaming.telephony.client.twilio_client import TwilioClient
from vocode.streaming.telephony.client.vonage_client import VonageClient


def create_telephony_client(
    base_url: str,
    maybe_twilio_config: Optional[TwilioConfig],
    maybe_vonage_config: Optional[VonageConfig],
) -> BaseTelephonyClient:
    if maybe_twilio_config is not None:
        return TwilioClient(base_url=base_url, twilio_config=maybe_twilio_config)
    elif maybe_vonage_config is not None:
        return VonageClient(base_url=base_url, vonage_config=maybe_vonage_config)
    else:
        raise ValueError("No telephony config provided")
