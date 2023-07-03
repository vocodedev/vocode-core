import pytest
import asyncio
from vocode.streaming.utils.worker import AsyncWorker
from vocode.streaming.pubsub.base_pubsub import (
    Publisher,
    PubSubManager,
)


@pytest.mark.asyncio
async def test_pubsub():
    pubsub = PubSubManager()

    sub1 = AsyncWorker(input_queue=asyncio.Queue())
    pubsub.subscribe(sub1, "topic1")
    pub = Publisher("pub")
    sub1.start()

    await pub.publish("1", "Hello, topic1!", "String", "topic1", pubsub)

    event = await sub1.input_queue.get()
    assert event.event_id == "1"
    assert event.payload == "Hello, topic1!"
    assert event.payload_type == "String"
    assert event.topic == "topic1"
