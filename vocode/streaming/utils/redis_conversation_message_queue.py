from typing import AsyncGenerator

from loguru import logger
from pydantic.v1 import BaseModel, parse_obj_as
from redis.asyncio import Redis

from vocode.streaming.utils.redis import initialize_redis
from vocode.streaming.utils.singleton import Singleton


class RedisMessage(BaseModel):
    type: str


class RedisConversationMessageQueue(Singleton):
    def __init__(self):
        self.redis: Redis = initialize_redis()

    async def publish(self, conversation_id: str, message: RedisMessage):
        logger.info(f"Publishing message to {conversation_id}")
        await self.redis.xadd(f"{conversation_id}:stream", message.dict())  # type: ignore

    async def wait_for_messages(
        self, conversation_id: str, timeout_seconds: int = 20
    ) -> AsyncGenerator[RedisMessage, None]:
        logger.info(f"Waiting for message from {conversation_id}")
        streams = await self.redis.xread(
            {f"{conversation_id}:stream": "$"}, block=timeout_seconds * 1000
        )
        for _, stream in streams:  # stream_id, stream
            for _, message in stream:  # timestamp, message
                yield parse_obj_as(RedisMessage, message)  # type: ignore

    async def clear_stream(self, conversation_id: str):
        await self.redis.delete(f"{conversation_id}:stream")
