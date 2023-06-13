from typing import Optional

from vocode.streaming.models.telephony import BaseCallConfig


class BaseConfigManager:
    async def save_config(self, conversation_id: str, config: BaseCallConfig):
        raise NotImplementedError

    async def get_config(self, conversation_id) -> Optional[BaseCallConfig]:
        raise NotImplementedError

    async def delete_config(self, conversation_id):
        raise NotImplementedError
