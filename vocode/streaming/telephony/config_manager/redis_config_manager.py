from typing import Optional

from loguru import logger
from redis import Redis

from vocode.streaming.models.telephony import BaseCallConfig
from vocode.streaming.telephony.config_manager.base_config_manager import BaseConfigManager
from vocode.streaming.utils.redis import initialize_redis


class RedisConfigManager(BaseConfigManager):
    def __init__(self):
        self.redis: Redis = initialize_redis()

    async def _set_with_one_day_expiration(self, *args, **kwargs):
        ONE_DAY_SECONDS = 60 * 60 * 24
        return await self.redis.set(*args, **{**kwargs, "ex": ONE_DAY_SECONDS})

    async def save_config(self, conversation_id: str, config: BaseCallConfig):
        logger.debug(f"Saving config for {conversation_id}")
        await self._set_with_one_day_expiration(conversation_id, config.json())

    async def get_config(self, conversation_id) -> Optional[BaseCallConfig]:
        logger.debug(f"Getting config for {conversation_id}")
        raw_config = await self.redis.get(conversation_id)  # type: ignore
        if raw_config:
            return BaseCallConfig.parse_raw(raw_config)
        return None

    async def delete_config(self, conversation_id):
        logger.debug(f"Deleting config for {conversation_id}")
        await self.redis.delete(conversation_id)
