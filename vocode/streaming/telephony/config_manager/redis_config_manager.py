from __future__ import annotations
import logging
import os
from typing import Optional
from redis.asyncio import Redis

from vocode.streaming.agent.command_agent import CommandAgent
from vocode.streaming.agent.state_agent import StateAgent, StateAgentState
from vocode.streaming.models.telephony import BaseCallConfig
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)
import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError


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

        self.models = {
            str(model): model for model in (CommandAgent, StateAgent, StateAgentState)
        }

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

    async def get(
        self, key: str
    ) -> Optional[CommandAgent | StateAgent | StateAgentState]:
        """Get and validate JSON from Redis using a Pydantic model"""
        value = await self.redis.get(key)

        if not value:
            return None
        try:
            value = json.loads(value)
            model_type = value.pop("__type")
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error for key {key}: {str(e)}")
            return None

        try:
            return self.models[model_type].parse_raw(value["data"])
        except ValidationError as e:
            self.logger.error(f"Validation error for key {key}: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error for key {key}: {str(e)}")
            return None

    async def set(self, key: str, value: BaseModel, expiry: int = 300) -> None:
        """
        Set a key-value pair in Redis with optional expiry in seconds
        Default to 5 minutes since that is the ~length of a call
        """
        assert isinstance(value, BaseModel)
        # Convert model to dict and add type info, pydantic serde is better
        json_str = json.dumps({"data": value.json(), "__type": str(type(value))})

        await self.redis.set(key, json_str, ex=expiry)

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def cleanup(self) -> None:
        if self.redis:
            await self.redis.close()
            self.redis = None
