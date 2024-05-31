from abc import ABC, abstractmethod
from typing import Dict, Optional

from vocode.streaming.models.telephony import TelephonyProviderConfig


class AbstractTelephonyClient(ABC):
    def __init__(self, base_url: str):
        self.base_url = base_url

    @abstractmethod
    def get_telephony_config(self) -> TelephonyProviderConfig:
        pass

    @abstractmethod
    async def create_call(
        self,
        conversation_id: str,
        to_phone: str,
        from_phone: str,
        record: bool = False,
        digits: Optional[str] = None,
        telephony_params: Optional[Dict[str, str]] = None,
    ) -> str:  # returns identifier of the call on the telephony provider
        pass

    @abstractmethod
    async def end_call(self, id) -> bool:
        raise NotImplementedError
