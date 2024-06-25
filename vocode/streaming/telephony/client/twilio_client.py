import os
from typing import Dict, Optional

import aiohttp
from loguru import logger

from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.telephony.client.abstract_telephony_client import AbstractTelephonyClient
from vocode.streaming.telephony.templater import get_connection_twiml
from vocode.streaming.utils.async_requester import AsyncRequestor


class TwilioBadRequestException(ValueError):
    pass


class TwilioException(ValueError):
    pass


class TwilioClient(AbstractTelephonyClient):
    def __init__(
        self,
        base_url: str,
        maybe_twilio_config: Optional[TwilioConfig] = None,
    ):
        self.twilio_config = maybe_twilio_config or TwilioConfig(
            account_sid=os.environ["TWILIO_ACCOUNT_SID"],
            auth_token=os.environ["TWILIO_AUTH_TOKEN"],
        )
        self.auth = aiohttp.BasicAuth(
            login=self.twilio_config.account_sid,
            password=self.twilio_config.auth_token,
        )
        super().__init__(base_url=base_url)

    def get_telephony_config(self):
        return self.twilio_config

    async def create_call(
        self,
        conversation_id: str,
        to_phone: str,
        from_phone: str,
        record: bool = False,  # currently no-op
        digits: Optional[str] = None,  # currently no-op
        telephony_params: Optional[Dict[str, str]] = None,
    ) -> str:
        data = {
            "Twiml": self.get_connection_twiml(conversation_id=conversation_id).body.decode(
                "utf-8"
            ),
            "To": f"+{to_phone}",
            "From": f"+{from_phone}",
            **(telephony_params or {}),
        }
        if digits:
            data["SendDigits"] = digits
        async with AsyncRequestor().get_session().post(
            f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_config.account_sid}/Calls.json",
            auth=self.auth,
            data=data,
        ) as response:
            if not response.ok:
                if response.status == 400:
                    logger.error(
                        f"Failed to create call: {response.status} {response.reason} {await response.json()}"
                    )
                    raise TwilioBadRequestException(
                        "Telephony provider rejected call; this is usually due to a bad/malformed number. "
                    )
                else:
                    raise TwilioException(
                        f"Twilio failed to create call: {response.status} {response.reason}"
                    )
            response = await response.json()
            return response["sid"]

    def get_connection_twiml(self, conversation_id: str):
        return get_connection_twiml(call_id=conversation_id, base_url=self.base_url)

    async def end_call(self, twilio_sid):
        async with AsyncRequestor().get_session().post(
            f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_config.account_sid}/Calls/{twilio_sid}.json",
            auth=self.auth,
            data={"Status": "completed"},
        ) as response:
            if not response.ok:
                raise RuntimeError(f"Failed to end call: {response.status} {response.reason}")
            response = await response.json()
            return response["status"] == "completed"
