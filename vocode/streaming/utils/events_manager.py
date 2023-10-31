from __future__ import annotations

import asyncio
import logging
import os
from typing import List, Optional

from redis import Redis

from vocode.streaming.models.events import Event, EventType


class RedisManager:
    def __init__(self, session_id: str, logger: Optional[logging.Logger] = None):
        self.session_id = session_id
        self.redis: Redis = Redis(
            host=os.environ['REDISHOST'],
            port=int(os.environ['REDISPORT']),
            username=os.environ['REDISUSER'],
            password=os.environ['REDISPASSWORD'],
            ssl=True,
            db=0,
            decode_responses=True,
        )
        self.logger = logger or logging.getLogger(__name__)

    async def save_log(self, message: str):
        self.logger.debug(f"Saving config for session id {self.session_id}")
        await self.redis.set(message)


class EventsManager:
    def __init__(self, subscriptions: List[EventType] = []):
        self.queue: asyncio.Queue[Event] = asyncio.Queue()
        self.subscriptions = set(subscriptions)
        self.active = False

    def publish_event(self, event: Event):
        if event.type in self.subscriptions:
            self.queue.put_nowait(event)

    async def start(self):
        self.active = True
        while self.active:
            try:
                event = await self.queue.get()
            except asyncio.QueueEmpty:
                await asyncio.sleep(1)
            await self.handle_event(event)

    async def handle_event(self, event: Event):
        pass

    async def flush(self):
        self.active = False
        while True:
            try:
                event = self.queue.get_nowait()
                await self.handle_event(event)
            except asyncio.QueueEmpty:
                break


class RedisEventsManager(EventsManager):
    def __init__(self, session_id: str, subscriptions: List[EventType] = []):
        super().__init__(subscriptions)
        self.redis_manager = RedisManager(session_id)

    async def handle_event(self, event: Event):
        # Log the event to Redis
        message = f"Event: {event.type}, Data: {event.data}"  # Adjust this based on the actual Event object structure
        await self.redis_manager.save_log(message)