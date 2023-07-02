import pytest
import asyncio
from vocode.streaming.pubsub.base_pubsub import (
    Event,
    Subscriber,
    Publisher,
    PubSubManager,
)


@pytest.mark.asyncio
async def test_pubsub():
    pubsub = PubSubManager()

    sub1 = Subscriber("sub1")
    pubsub.subscribe(sub1, "topic1")

    pub = Publisher("pub")

    await pub.publish("1", "Hello, topic1!", "String", "topic1", pubsub)

    event = await sub1.queue.get()
    assert event.id == "1"
    assert event.payload == "Hello, topic1!"
    assert event.payload_type == "String"
    assert event.topic == "topic1"
