from typing import Optional
import aiohttp
from vocode.streaming.models.telephony import VonageConfig
from vocode.streaming.telephony.client.base_telephony_client import BaseTelephonyClient
import vonage

from vocode.streaming.telephony.constants import VONAGE_CONTENT_TYPE


class VonageClient(BaseTelephonyClient):
    def __init__(self, base_url, vonage_config: VonageConfig):
        super().__init__(base_url)
        self.vonage_config = vonage_config
        self.client = vonage.Client(
            key=vonage_config.api_key,
            secret=vonage_config.api_secret,
            application_id=vonage_config.application_id,
            private_key=vonage_config.private_key,
        )
        self.voice = vonage.Voice(self.client)

    def get_telephony_config(self):
        return self.vonage_config

    def create_call(
        self,
        conversation_id: str,
        to_phone: str,
        from_phone: str,
        record: bool = False,
        digits: Optional[str] = None,
    ) -> str:  # identifier of the call on the telephony provider
        response = self.voice.create_call(
            {
                "to": [{"type": "phone", "number": to_phone, "dtmfAnswer": digits}],
                "from": {"type": "phone", "number": from_phone},
                "ncco": self.create_call_ncco(self.base_url, conversation_id, record),
            }
        )
        if response["status"] != "started":
            raise RuntimeError(f"Failed to start call: {response}")
        return response["uuid"]

    @staticmethod
    def create_call_ncco(base_url, conversation_id, record):
        ncco = []
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
        async with aiohttp.ClientSession() as session:
            async with session.put(
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
        return True

    # TODO(EPD-186)
    def validate_outbound_call(
        self,
        to_phone: str,
        from_phone: str,
        mobile_only: bool = True,
    ):
        pass
