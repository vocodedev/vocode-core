from __future__ import annotations

import asyncio
from typing import List

from loguru import logger

from vocode.streaming.models.events import Event, EventType


class EventsManager:
    def __init__(self, subscriptions: List[EventType] = []):
        self.queue: asyncio.Queue[Event] = asyncio.Queue()
        self.subscriptions = set(subscriptions)
        self.active = False

    def publish_event(self, event: Event):
        if event and event.type in self.subscriptions:
            self.queue.put_nowait(event)

    async def start(self):
        self.active = True
        while self.active:
            try:
                event = await self.queue.get()
            except asyncio.QueueEmpty:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
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
            except TypeError as e:
                if "NoneType can't be used in 'await' expression" in str(e):
                    logger.error(
                        "Handle event was overridden with non-async function. Please override with async function."
                    )
                else:
                    raise e from e
