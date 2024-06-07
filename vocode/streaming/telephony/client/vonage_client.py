import os
from typing import Any, Dict, List, Optional

from vocode.streaming.models.telephony import VonageConfig
from vocode.streaming.telephony.client.abstract_telephony_client import AbstractTelephonyClient
from vocode.streaming.telephony.constants import VONAGE_CONTENT_TYPE
from vocode.streaming.utils.async_requester import AsyncRequestor


class VonageBadRequestException(ValueError):
    pass


class VonageClient(AbstractTelephonyClient):
    def __init__(
        self,
        base_url: str,
        maybe_vonage_config: Optional[VonageConfig] = None,
        record_calls: bool = False,
    ):

        import vonage

        self.vonage = vonage

        super().__init__(
            base_url=base_url,
        )
        self.vonage_config = maybe_vonage_config or VonageConfig(
            api_key=os.environ["VONAGE_API_KEY"],
            api_secret=os.environ["VONAGE_API_SECRET"],
            application_id=os.environ["VONAGE_APPLICATION_ID"],
            private_key=os.environ["VONAGE_PRIVATE_KEY"],
            record=record_calls,
        )
        # Vonage's sync client: only used for authentication helpers
        self.client = self.vonage.Client(
            key=self.vonage_config.api_key,
            secret=self.vonage_config.api_secret,
            application_id=self.vonage_config.application_id,
            private_key=self.vonage_config.private_key,
        )

    def get_telephony_config(self):
        return self.vonage_config

    async def create_call(
        self,
        conversation_id: str,
        to_phone: str,
        from_phone: str,
        record: bool = False,
        digits: Optional[str] = None,
        telephony_params: Optional[Dict[str, str]] = None,
    ) -> str:  # identifier of the call on the telephony provider
        return await self._create_vonage_call(
            to_phone,
            from_phone,
            self.create_call_ncco(
                conversation_id=conversation_id,
                record=record,
                is_outbound=True,
            ),
            digits,
            event_urls=[],
        )

    async def end_call(self, id) -> bool:
        async with AsyncRequestor().get_session().put(
            f"https://api.nexmo.com/v1/calls/{id}",
            json={"action": "hangup"},
            headers={"Authorization": f"Bearer {self.client._generate_application_jwt().decode()}"},
        ) as response:
            if not response.ok:
                raise RuntimeError(f"Failed to end call: {response.status} {response.reason}")
        return True

    async def update_call(self, vonage_uuid, new_ncco):
        async with AsyncRequestor().get_session().put(
            f"https://api.nexmo.com/v1/calls/{vonage_uuid}",
            json={
                "action": "transfer",
                "destination": {"type": "ncco", "ncco": new_ncco},
            },
            headers={"Authorization": self.client._create_jwt_auth_string().decode()},
        ) as response:
            if not response.ok:
                raise RuntimeError(f"Failed to update call: {response.status} {response.reason}")
            return True

    def create_call_ncco(
        self,
        conversation_id,
        record,  # currently no-op
        is_outbound: bool = False,
    ):
        ncco: List[Dict[str, Any]] = []
        ncco.append(
            {
                "action": "connect",
                "endpoint": [
                    {
                        "type": "websocket",
                        "uri": f"wss://{self.base_url}/connect_call/{conversation_id}",
                        "content-type": VONAGE_CONTENT_TYPE,
                        "headers": {},
                    }
                ],
            },
        )
        return ncco

    async def _create_vonage_call(
        self,
        to_phone: str,
        from_phone: str,
        ncco: str,
        digits: Optional[str] = None,
        event_urls: List[str] = [],
        **kwargs,
    ) -> str:  # returns the Vonage UUID
        vonage_call_uuid: str
        async with AsyncRequestor().get_session().post(
            "https://api.nexmo.com/v1/calls",
            json={
                "to": [{"type": "phone", "number": to_phone, "dtmfAnswer": digits}],
                "from": {"type": "phone", "number": from_phone},
                "ncco": ncco,
                "event_url": event_urls,
                **kwargs,
            },
            headers={"Authorization": f"Bearer {self.client._generate_application_jwt().decode()}"},
        ) as response:
            if not response.ok:
                if response.status == 400:
                    raise VonageBadRequestException(
                        "Failed to start call; this is usually due to a bad/malformed number. "
                        "If this persists, and you're sure that the number is well-formed, "
                        "please contact us."
                    )
                raise RuntimeError(f"Failed to start call: {response.status} {response.reason}")
            data = await response.json()
            if not data["status"] == "started":
                raise RuntimeError(f"Failed to start call: {response}")
            vonage_call_uuid = data["uuid"]
        return vonage_call_uuid

    async def send_dtmf(self, vonage_uuid: str, digits: str):
        async with AsyncRequestor().get_session().put(
            f"https://api.nexmo.com/v1/calls/{vonage_uuid}/dtmf",
            json={"digits": digits},
            headers={"Authorization": self.client._create_jwt_auth_string().decode()},
        ) as response:
            if not response.ok:
                raise RuntimeError(f"Failed to send DTMF: {response.status} {response.reason}")
            await response.json()
