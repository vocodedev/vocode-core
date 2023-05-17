import asyncio
import queue
from typing import Generic, TypeVar


AsyncQueueElement = TypeVar("AsyncQueueElement")
SyncQueueElement = TypeVar("SyncQueueElement")


class AsyncQueueType(asyncio.Queue, Generic[AsyncQueueElement]):
    pass


class SyncQueueType(queue.Queue, Generic[SyncQueueElement]):
    pass
