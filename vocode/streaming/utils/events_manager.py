from __future__ import annotations
import asyncio


from vocode.streaming.models.events import Event


async def flush_event(event):
    if event:
        del event


class EventsManager:
    def __init__(self, subscriptions=None):
        if subscriptions is None:
            subscriptions = []
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
                await self.handle_event(event)
            except asyncio.QueueEmpty:
                await asyncio.sleep(1)

    async def handle_event(self, event: Event):
        pass  # Default implementation, can be overridden

    async def flush(self, timeout=30):
        while True:
            try:
                event = await asyncio.wait_for(self.queue.get(), timeout)
                await flush_event(event)
            except asyncio.TimeoutError:
                break
            except asyncio.QueueEmpty:
                break
