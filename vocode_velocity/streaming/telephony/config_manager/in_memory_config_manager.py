from typing import Optional

from vocode.streaming.models.telephony import BaseCallConfig
from vocode.streaming.telephony.config_manager.base_config_manager import BaseConfigManager


class InMemoryConfigManager(BaseConfigManager):
    def __init__(self):
        self.configs = {}

    async def save_config(self, conversation_id: str, config: BaseCallConfig):
        self.configs[conversation_id] = config

    async def get_config(self, conversation_id) -> Optional[BaseCallConfig]:
        return self.configs.get(conversation_id)

    async def delete_config(self, conversation_id):
        if conversation_id in self.configs:
            del self.configs[conversation_id]
