from typing import Optional

from vocode.streaming.models.telephony import BaseCallConfig


class BaseTelephonyClient:
    def __init__(self, base_url):
        self.base_url = base_url

    def get_telephony_config(self):
        raise NotImplementedError

    async def create_call(
        self,
        conversation_id: str,
        to_phone: str,
        from_phone: str,
        record: bool = False,
        digits: Optional[str] = None,
    ) -> str:  # identifier of the call on the telephony provider
        raise NotImplementedError

    async def end_call(self, id) -> bool:
        raise NotImplementedError

    def validate_outbound_call(
        self,
        to_phone: str,
        from_phone: str,
        mobile_only: bool = True,
    ):
        raise NotImplementedError
