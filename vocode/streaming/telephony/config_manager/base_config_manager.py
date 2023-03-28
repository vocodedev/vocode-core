import logging
from typing import Optional
from redis import Redis

from vocode.streaming.models.telephony import CallConfig


class BaseConfigManager:
    def save_config(self, conversation_id: str, config: CallConfig):
        raise NotImplementedError

    def get_config(self, conversation_id) -> Optional[CallConfig]:
        raise NotImplementedError

    def delete_config(self, conversation_id):
        raise NotImplementedError
