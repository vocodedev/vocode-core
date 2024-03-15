import asyncio
import json
import logging
import os
import time
from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import ConnectionError

from vocode.streaming.models.telephony import BaseCallConfig
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)


class RedisConfigManager(BaseConfigManager):

    def __init__(self, logger: Optional[logging.Logger] = None):
        self._build_redis()
        self.logger = logger or logging.getLogger(__name__)

    def _build_redis(self):
        self.redis = Redis(
            host=os.environ.get("REDISHOST", "localhost"),
            port=int(os.environ.get("REDISPORT", 6379)),
            username=os.environ.get("REDISUSER", None),
            password=os.environ.get("REDISPASSWORD", None),
            db=os.environ['REDISDB'],
            decode_responses=True,
            ssl=True,
        )

    async def _reconnect_redis(self):
        self.logger.info("Reconnecting to Redis.")
        await self.redis.close()  # Close the existing connection
        await self.redis.connection_pool.disconnect()  # Disconnect the connection pool
        self._build_redis()
        await self.redis.ping()

    async def save_config(self, conversation_id: str, config: BaseCallConfig) -> None:
        # FIXME: resolve blocking calls that might cause the error, try to use bigger timeout.
        self.logger.debug(f"Saving config for {conversation_id}")
        for attempt in range(3):  # Retry up to 3 times
            try:
                await self.redis.setex(conversation_id, 60 * 60, config.json())
            except ConnectionError as e:
                self.logger.warning(f"Attempt {attempt + 1}: Connection error: {e}")
                if attempt < 2:
                    await self._reconnect_redis()
                else:
                    self.logger.error("Final attempt failed. Unable to get config.")
                    raise
            except Exception as e:
                self.logger.error(f"An unexpected error occurred: {e}")
                raise
            await asyncio.sleep(0.5)

    async def get_config(self, conversation_id: str) -> Optional[BaseCallConfig]:
        self.logger.debug(f"Getting config for {conversation_id}")
        for attempt in range(3):  # Retry up to 3 times
            try:
                raw_config = await self.redis.get(conversation_id)
                if raw_config:
                    return BaseCallConfig.parse_raw(raw_config)
            except ConnectionError as e:
                self.logger.warning(f"Attempt {attempt + 1}: Connection error: {e}")
                if attempt < 2:
                    await self._reconnect_redis()
                else:
                    self.logger.error("Final attempt failed. Unable to get config.")
                    raise
            except Exception as e:
                self.logger.error(f"An unexpected error occurred: {e}")
                raise
            await asyncio.sleep(0.5)
        return None

    async def delete_config(self, conversation_id):
        self.logger.debug(f"Deleting config for {conversation_id}")
        for attempt in range(3):  # Retry up to 3 times
            try:
                await self.redis.delete(conversation_id)
            except ConnectionError as e:
                self.logger.warning(f"Attempt {attempt + 1}: Connection error: {e}")
                if attempt < 2:
                    await self._reconnect_redis()
                else:
                    self.logger.error("Final attempt failed. Unable to get config.")
                    raise
            except Exception as e:
                self.logger.error(f"An unexpected error occurred: {e}")
                raise
            await asyncio.sleep(0.5)

    async def get_inbound_dialog_state(self, phone: str) -> Optional[dict]:
        self.logger.debug(f"Getting inbound dialog state for {phone}")
        key = f"inbound_dialog_state:{phone}"
        for attempt in range(3):  # Retry up to 3 times
            try:
                raw_state = await self.redis.get(key)
                if raw_state:
                    return json.loads(raw_state)
                return None
            except ConnectionError as e:
                self.logger.warning(f"Attempt {attempt + 1}: Connection error: {e}")
                if attempt < 2:
                    await self._reconnect_redis()
                else:
                    self.logger.error("Final attempt failed. Unable to get config.")
                    raise
            except Exception as e:
                self.logger.error(f"An unexpected error occurred: {e}")
                raise
            await asyncio.sleep(0.5)

    async def log_call_state(self, telephony_id: str, state: str, **kwargs):

        for attempt in range(3):  # Retry up to 3 times
            try:
                await self.redis.setex(f"call_state:{telephony_id}:{state}:{time.time()}", 60 * 60 * 24 * 7,
                                       json.dumps(kwargs))
            except ConnectionError as e:
                self.logger.warning(f"Attempt {attempt + 1}: Connection error: {e}")
                if attempt < 2:
                    await self._reconnect_redis()
                else:
                    self.logger.error("Final attempt failed. Unable to get config.")
                    raise
            except Exception as e:
                self.logger.error(f"An unexpected error occurred: {e}")
                raise
            await asyncio.sleep(0.5)
