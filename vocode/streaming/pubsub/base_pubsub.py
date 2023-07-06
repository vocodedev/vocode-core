import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List
from time import time
import audioop

import numpy as np

from vocode.streaming.utils.worker import AsyncWorker
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.output_device.file_output_device import FileOutputDevice


@dataclass
class PubsubEvent:
    """Event Dataclass contains details about the event."""

    event_id: str
    payload: Any
    payload_type: str
    timestamp: str
    topic: str


class AudioFileWriterSubscriber(AsyncWorker):
    """Subscriber class which listens to topics it is subscribed to."""

    def __init__(self, name: str, sampling_rate=8000):
        self.name = name
        self.input_queue = asyncio.Queue()
        self.file_writers: Dict[int, FileOutputDevice] = {}
        self.buffers: Dict[int, List[np.ndarray]] = {}
        self.last_flush_time: Dict[int, float] = {}
        self.save_chunk_in_sec = 5
        self.sampling_rate = sampling_rate
        super().__init__(input_queue=self.input_queue)

    async def _run_loop(self):
        """Listen to the topics subscribed to."""
        while True:
            event = await self.input_queue.get()
            if event is None:
                continue

            if event.payload_type == AudioEncoding.MULAW:
                payload = audioop.ulaw2lin(event.payload, 2)
            else:
                payload = event.payload

            if event.event_id not in self.file_writers:
                self.file_writers[event.event_id] = FileOutputDevice(
                    f"recordings/{event.event_id}.wav",
                    sampling_rate=self.sampling_rate,
                    audio_encoding=event.payload_type,
                )
                self.buffers[event.event_id] = []
                self.last_flush_time[event.event_id] = time()
            self.buffers[event.event_id].append(payload)
            if time() - self.last_flush_time[event.event_id] >= self.save_chunk_in_sec:
                for chunk in self.buffers[event.event_id]:
                    self.file_writers[event.event_id].consume_nonblocking(chunk)
                self.buffers[event.event_id] = []
                self.last_flush_time[event.event_id] = time()

    def terminate(self):
        for writer in self.file_writers.values():
            writer.terminate()
        AsyncWorker.terminate(self)


class PubSubManager:
    """Manages subscribers and publishers."""

    def __init__(self):
        self.subscribers: Dict[str, List[AsyncWorker]] = {}

    def subscribe(self, subscriber: AsyncWorker, topic: str):
        """Subscriber subscribes to a specific topic."""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(subscriber)

    async def publish(self, event: PubsubEvent):
        """Publish an event to a specific topic."""
        for subscriber in self.subscribers.get(event.topic, []):
            await subscriber.input_queue.put(event)


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

        event = PubsubEvent(
            event_id, payload, payload_type, datetime.utcnow().isoformat(), topic
        )
        await pubsub.publish(event)
