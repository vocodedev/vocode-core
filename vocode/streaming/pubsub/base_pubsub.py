import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List
from time import time

import numpy as np

from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.output_device.file_output_device import FileOutputDevice


@dataclass
class Event:
    """Event Dataclass contains details about the event."""

    id: str
    payload: Any
    payload_type: str
    timestamp: str
    topic: str


class Subscriber:
    """Subscriber class which listens to topics it is subscribed to."""

    def __init__(self, name: str):
        self.name = name
        self.queue = asyncio.Queue()

    async def listen(self):
        """Listen to the topics subscribed to."""
        while True:
            event = await self.queue.get()
            print(
                f"[{self.name}] Received event {event.event_id} on topic {event.topic} at {event.timestamp} with type: {event.payload_type}"
            )


class AudioFileWriterSubscriber:
    """Subscriber class which listens to topics it is subscribed to."""

    def __init__(self, name: str):
        self.name = name
        self.queue = asyncio.Queue()
        self.file_writers: Dict[int, FileOutputDevice] = {}
        self.buffers: Dict[int, List[np.ndarray]] = {}
        self.last_flush_time: Dict[int, float] = {}
        self.save_chunk_in_sec = 15

    async def listen(self):
        """Listen to the topics subscribed to."""
        while True:
            event = await self.queue.get()
            if event.payload_type == AudioEncoding.LINEAR16:
                # accomulate 15 seconds chunks based on event.id and flush them to disk to recording/{event.id}.wav
                if event.id not in self.file_writers:
                    self.file_writers[event.id] = FileOutputDevice(
                        f"recordings/{event.id}.wav"
                    )
                    self.buffers[event.id] = []
                    self.last_flush_time[event.id] = time()
                self.buffers[event.id].append(event.payload)
                if time() - self.last_flush_time[event.id] >= self.save_chunk_in_sec:
                    for chunk in self.buffers[event.id]:
                        self.file_writers[event.id].consume_nonblocking(chunk)
                    self.buffers[event.id] = []
                    self.last_flush_time[event.id] = time()

    async def close(self):
        for writer in self.file_writers.values():
            writer.terminate()


class PubSubManager:
    """Manages subscribers and publishers."""

    def __init__(self):
        self.subscribers: Dict[str, List[Subscriber]] = {}

    def subscribe(self, subscriber: Subscriber, topic: str):
        """Subscriber subscribes to a specific topic."""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(subscriber)

    async def publish(self, event: Event):
        """Publish an event to a specific topic."""
        for subscriber in self.subscribers.get(event.topic, []):
            await subscriber.queue.put(event)


class Publisher:
    """Publisher class which publishes events."""

    def __init__(self, name: str):
        self.name = name

    async def publish(
        self,
        event_id: str,
        payload: Any,
        payload_type: str,
        topic: str = "audio",
        pubsub: PubSubManager = None,
    ):
        """Publish an event to a specific topic."""

        if pubsub is None:
            raise ValueError(
                "pubsub can not be None when publishing events via Publisher.publish"
            )

        event = Event(
            event_id, payload, payload_type, datetime.utcnow().isoformat(), topic
        )
        await pubsub.publish(event)
