from os import getenv
from typing import Optional
from vocode.streaming.telephony.client.base_telephony_client import BaseTelephonyClient
import vonage


class VonageClient(BaseTelephonyClient):
    def __init__(self, base_url):
        super().__init__(base_url)
        self.client = vonage.Client(
            key=getenv("VONAGE_API_KEY"),
            secret=getenv("VONAGE_API_SECRET"),
            application_id=getenv("VONAGE_APPLICATION_ID"),
            private_key=getenv("VONAGE_PRIVATE_KEY"),
        )
        self.voice = vonage.Voice(self.client)

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
                "to": [{"type": "phone", "number": to_phone}],
                "from": {"type": "phone", "number": from_phone},
                "ncco": [
                    {
                        "action": "connect",
                        "endpoint": [
                            {
                                "type": "websocket",
                                "uri": f"wss://{self.base_url}/connect_call/{conversation_id}",
                                "content-type": "audio/l16;rate=16000",
                                "headers": {},
                            }
                        ],
                    }
                ],
            }
        )
        print(response)
        return "foo"

    def end_call(self, id) -> bool:
        raise NotImplementedError

    def validate_outbound_call(
        self,
        to_phone: str,
        from_phone: str,
        mobile_only: bool = True,
    ):
        pass
