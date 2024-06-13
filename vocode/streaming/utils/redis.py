import os
from typing import Optional, TypeVar

from loguru import logger
from redis.asyncio import Redis
from redis.backoff import ExponentialBackoff, NoBackoff
from redis.exceptions import ConnectionError, TimeoutError
from redis.retry import Retry

from vocode.streaming.utils.singleton import Singleton

WorkerInputType = TypeVar("WorkerInputType")
# Two separate factories for Redis clients so that the
# typing gets picked up properly


def initialize_redis(retries: int = 1):
    backoff = ExponentialBackoff() if retries > 1 else NoBackoff()
    retry = Retry(backoff, retries)
    return Redis(  # type: ignore
        host=os.environ.get("REDISHOST", "localhost"),
        port=int(os.environ.get("REDISPORT", 6379)),
        username=os.environ.get("REDISUSER", None),
        password=os.environ.get("REDISPASSWORD", None),
        decode_responses=True,
        retry=retry,
        ssl=bool(os.environ.get("REDISSSL", False)),
        ssl_cert_reqs="none",
        retry_on_error=[ConnectionError, TimeoutError],
        health_check_interval=30,
    )


def initialize_redis_bytes():
    return Redis(
        host=os.environ.get("REDISHOST", "localhost"),
        port=int(os.environ.get("REDISPORT", 6379)),
        username=os.environ.get("REDISUSER", None),
        password=os.environ.get("REDISPASSWORD", None),
        db=0,
        ssl=bool(os.environ.get("REDISSSL", False)),
        ssl_cert_reqs="none",
    )


class RedisGenericMessageQueue(Singleton):
    """Class representing a Redis Streams message queue."""

    def __init__(
        self,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
    ) -> None:
        """
        Initialize a RedisGenericMessageQueue instance.

        This initializes a Redis client and sets the name of the stream.
        """
        self.redis: Redis = initialize_redis()
        queue_name_prefix = f"{prefix}_" if prefix else ""
        queue_name_suffix = f"_{suffix}" if suffix else ""
        self.queue_name = f"{queue_name_prefix}queue{queue_name_suffix}"

    async def publish(self, message: dict) -> None:
        """
        Publishes a message to the Redis stream.

        Args:
            message (dict): The message to be published.

        Returns:
            None
        """
        logger.info(f"[{self.queue_name}] Publishing message: {message}")
        try:
            await self.redis.xadd(self.queue_name, message)
        except Exception as e:
            logger.exception(f"[{self.queue_name}] Failed to publish message: {message}")
            raise e
