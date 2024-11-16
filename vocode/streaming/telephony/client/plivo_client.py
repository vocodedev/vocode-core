import os
from typing import Dict, Optional

import aiohttp

from loguru import logger

from vocode.streaming.models.telephony import PlivoConfig
from vocode.streaming.telephony.client.abstract_telephony_client import AbstractTelephonyClient
from vocode.streaming.telephony.templater import get_connection_plivoxml
from vocode.streaming.utils.async_requester import AsyncRequestor


class PlivoBadRequestException(ValueError):
    pass


class PlivoException(ValueError):
    pass


class PlivoClient(AbstractTelephonyClient):
    def __init__(
        self,
        base_url: str,
        maybe_plivo_config: Optional[PlivoConfig] = None,
    ):
        self.plivo_config = maybe_plivo_config or PlivoConfig(
            auth_id=os.environ["PLIVO_AUTH_ID"],
            auth_token=os.environ["PLIVO_AUTH_TOKEN"],
        )
        self.auth = aiohttp.BasicAuth(
            login=self.plivo_config.auth_id,
            password=self.plivo_config.auth_token,
        )
        super().__init__(base_url=base_url)

    def get_telephony_config(self):
        return self.plivo_config

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
            "Plivoxml": self.get_connection_plivoxml(conversation_id=conversation_id).body.decode(
                "utf-8"
            ),
            "To": f"+{to_phone}",
            "From": f"+{from_phone}",
            **(telephony_params or {}),
        }
        if digits:
            data["SendDigits"] = digits
        async with AsyncRequestor().get_session().post(
            f"https://api.plivo.com/v1/Account/{self.plivo_config.auth_id}/Call/",
            auth=self.auth,
            data=data,
        ) as response:
            if not response.ok:
                if response.status == 400:
                    logger.warning(
                        f"Failed to create call: {response.status} {response.reason} {await response.json()}"
                    )
                    raise PlivoBadRequestException(
                        "Telephony provider rejected call; this is usually due to a bad/malformed number. "
                    )
                else:
                    raise PlivoException(
                        f"Plivo failed to create call: {response.status} {response.reason}"
                    )
            response = await response.json()
            return response["sid"]

    # TODO: Plivo Integration
    def get_connection_plivoxml(self, conversation_id: str):
        return get_connection_plivoxml(call_id=conversation_id, base_url=self.base_url)

    async def end_call(self, plivo_sid):
        logger.debug(f"Auth: {self.auth}")
  
        async with AsyncRequestor().get_session().post(
            f"https://api.plivo.com/v1/Account/{self.plivo_config.auth_id}/Call/{plivo_sid}",
            auth=self.auth,
            data={"Status": "completed"},
        ) as response:
            
            if not response.ok:
                raise RuntimeError(f"Failed to end call: {response.status} {response.reason}")
            response = await response.json()
            return response["status"] == "completed"
