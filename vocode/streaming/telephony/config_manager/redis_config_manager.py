import logging
import os
from typing import Optional
from redis.asyncio import Redis

from vocode.streaming.models.telephony import BaseCallConfig
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)


class RedisConfigManager(BaseConfigManager):
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.redis: Redis = Redis(
            host=os.environ.get("REDISHOST", "localhost"),
            port=int(os.environ.get("REDISPORT", 6379)),
            username=os.environ.get("REDISUSER", None),
            password=os.environ.get("REDISPASSWORD", None),
            db=0,
            decode_responses=True,
        )
        self.logger = logger or logging.getLogger(__name__)

    async def save_config(self, conversation_id: str, config: BaseCallConfig):
        self.logger.debug(f"Saving config for {conversation_id}")
        await self.redis.set(conversation_id, config.json())

    async def get_config(self, conversation_id) -> Optional[BaseCallConfig]:
        self.logger.debug(f"Getting config for {conversation_id}")
        raw_config = await self.redis.get(conversation_id)
        if raw_config:
            return BaseCallConfig.parse_raw(raw_config)
        return None

    async def delete_config(self, conversation_id):
        self.logger.debug(f"Deleting config for {conversation_id}")
        await self.redis.delete(conversation_id)
