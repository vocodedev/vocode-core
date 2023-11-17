from typing import Any, Dict, List, Optional
import aiohttp
from vocode.streaming.models.telephony import VonageConfig
from vocode.streaming.telephony.client.base_telephony_client import BaseTelephonyClient
import vonage

from vocode.streaming.telephony.constants import VONAGE_CONTENT_TYPE


class VonageClient(BaseTelephonyClient):
    def __init__(
        self,
        base_url,
        vonage_config: VonageConfig,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(base_url)
        self.vonage_config = vonage_config
        self.client = vonage.Client(
            key=vonage_config.api_key,
            secret=vonage_config.api_secret,
            application_id=vonage_config.application_id,
            private_key=vonage_config.private_key,
        )
        self.voice = vonage.Voice(self.client)
        self.maybe_aiohttp_session = aiohttp_session

    def get_telephony_config(self):
        return self.vonage_config

    async def create_vonage_call(
        self,
        to_phone: str,
        from_phone: str,
        ncco: str,
        digits: Optional[str] = None,
        event_urls: List[str] = [],
        **kwargs,
    ) -> str:  # returns the Vonage UUID
        aiohttp_session = self.maybe_aiohttp_session or aiohttp.ClientSession()
        vonage_call_uuid: str
        async with aiohttp_session.post(
            f"https://api.nexmo.com/v1/calls",
            json={
                "to": [{"type": "phone", "number": to_phone, "dtmfAnswer": digits}],
                "from": {"type": "phone", "number": from_phone},
                "ncco": ncco,
                "event_url": event_urls,
                **kwargs,
            },
            headers={
                "Authorization": f"Bearer {self.client._generate_application_jwt().decode()}"
            },
        ) as response:
            if not response.ok:
                raise RuntimeError(
                    f"Failed to start call: {response.status} {response.reason}"
                )
            data = await response.json()
            if not data["status"] == "started":
                raise RuntimeError(f"Failed to start call: {response}")
            vonage_call_uuid = data["uuid"]
        if not self.maybe_aiohttp_session:
            await aiohttp_session.close()
        return vonage_call_uuid

    async def create_call(
        self,
        conversation_id: str,
        to_phone: str,
        from_phone: str,
        record: bool = False,
        digits: Optional[str] = None,
    ) -> str:  # identifier of the call on the telephony provider
        return await self.create_vonage_call(
            to_phone,
            from_phone,
            self.create_call_ncco(
                self.base_url, conversation_id, record, is_outbound=True
            ),
            digits,
        )

    @staticmethod
    def create_call_ncco(base_url, conversation_id, record, is_outbound: bool = False):
        ncco: List[Dict[str, Any]] = []
        if record:
            ncco.append(
                {
                    "action": "record",
                    "eventUrl": [f"https://{base_url}/recordings/{conversation_id}"],
                }
            )
        ncco.append(
            {
                "action": "connect",
                "endpoint": [
                    {
                        "type": "websocket",
                        "uri": f"wss://{base_url}/connect_call/{conversation_id}",
                        "content-type": VONAGE_CONTENT_TYPE,
                        "headers": {},
                    }
                ],
            }
        )
        return ncco

    async def end_call(self, id) -> bool:
        aiohttp_session = self.maybe_aiohttp_session or aiohttp.ClientSession()
        async with aiohttp_session.put(
            f"https://api.nexmo.com/v1/calls/{id}",
            json={"action": "hangup"},
            headers={
                "Authorization": f"Bearer {self.client._generate_application_jwt().decode()}"
            },
        ) as response:
            if not response.ok:
                raise RuntimeError(
                    f"Failed to end call: {response.status} {response.reason}"
                )
        if not self.maybe_aiohttp_session:
            await aiohttp_session.close()
        return True

    # TODO(EPD-186)
    def validate_outbound_call(
        self,
        to_phone: str,
        from_phone: str,
        mobile_only: bool = True,
    ):
        pass
