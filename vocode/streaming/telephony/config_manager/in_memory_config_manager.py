from typing import Optional
from vocode.streaming.models.telephony import CallConfig
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)


class InMemoryConfigManager(BaseConfigManager):
    def __init__(self):
        self.configs = {}

    def save_config(self, conversation_id: str, config: CallConfig):
        self.configs[conversation_id] = config

    def get_config(self, conversation_id) -> Optional[CallConfig]:
        return self.configs.get(conversation_id)

    def delete_config(self, conversation_id):
        del self.configs[conversation_id]
