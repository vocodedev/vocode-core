from typing import Optional

from vocode.streaming.models.telephony import BaseCallConfig


class BaseConfigManager:
    async def save_config(self, conversation_id: str, config: BaseCallConfig):
        raise NotImplementedError

    async def get_config(self, conversation_id) -> Optional[BaseCallConfig]:
        raise NotImplementedError

    async def delete_config(self, conversation_id):
        raise NotImplementedError

    async def get_inbound_dialog_state(self, phone: str) -> Optional[dict]:
        raise NotImplementedError

    def create_id_router(self, conversation_id, internal_id):
        pass

    async def log_call_state(self, telephony_id: str, state: str, **kwargs):
        pass