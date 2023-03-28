import logging
import os
from typing import Optional
from redis import Redis

from vocode.streaming.models.telephony import CallConfig
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)


class RedisConfigManager(BaseConfigManager):
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.redis = Redis(
            host=os.environ.get("REDISHOST", "localhost"),
            port=int(os.environ.get("REDISPORT", 6379)),
            db=0,
            decode_responses=True,
        )
        self.logger = logger or logging.getLogger(__name__)

    def save_config(self, conversation_id: str, config: CallConfig):
        self.logger.debug(f"Saving config for {conversation_id}")
        self.redis.set(conversation_id, config.json())

    def get_config(self, conversation_id) -> Optional[CallConfig]:
        self.logger.debug(f"Getting config for {conversation_id}")
        raw_config = self.redis.get(conversation_id)
        if raw_config:
            return CallConfig.parse_raw(self.redis.get(conversation_id))

    def delete_config(self, conversation_id):
        self.logger.debug(f"Deleting config for {conversation_id}")
        self.redis.delete(conversation_id)
