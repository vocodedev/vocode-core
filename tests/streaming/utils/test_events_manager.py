import asyncio

import pytest

from vocode.streaming.models.events import EventType, PhoneCallEndedEvent
from vocode.streaming.utils.events_manager import EventsManager

CONVERSATION_ID = "1"


@pytest.mark.asyncio
async def test_initialization():
    manager = EventsManager()
    assert manager.subscriptions == set()
    assert isinstance(manager.queue, asyncio.Queue)
    assert not manager.active


@pytest.mark.asyncio
async def test_publish_event():
    event = PhoneCallEndedEvent(
        conversation_id=CONVERSATION_ID, type=EventType.PHONE_CALL_ENDED
    )  # Replace with actual Event creation
    manager = EventsManager([EventType.PHONE_CALL_ENDED])
    manager.publish_event(event)
    assert not manager.queue.empty()


@pytest.mark.asyncio
async def test_handle_event_default_implementation():
    event = PhoneCallEndedEvent(
        conversation_id=CONVERSATION_ID, type=EventType.PHONE_CALL_ENDED
    )  # Replace with actual Event creation
    manager = EventsManager([EventType.PHONE_CALL_ENDED])
    await manager.handle_event(event)


@pytest.mark.asyncio
async def test_handle_event_non_async_override(mocker):
    event = PhoneCallEndedEvent(conversation_id=CONVERSATION_ID, type=EventType.PHONE_CALL_ENDED)
    manager = EventsManager([EventType.PHONE_CALL_ENDED])
    manager.publish_event(event)

    error_logger_mock = mocker.patch("vocode.streaming.utils.events_manager.logger.error")
    manager.handle_event = lambda event: None
    await manager.flush()
    assert manager.queue.empty()
    error_logger_mock.assert_called_once_with(
        "Handle event was overridden with non-async function. Please override with async function."
    )


@pytest.mark.asyncio
async def test_start_and_active_loop():
    event = PhoneCallEndedEvent(
        conversation_id=CONVERSATION_ID, type=EventType.PHONE_CALL_ENDED
    )  # Replace with actual Event creation
    manager = EventsManager([EventType.PHONE_CALL_ENDED])
    asyncio.create_task(manager.start())
    manager.publish_event(event)
    await asyncio.sleep(0.1)
    manager.active = False


@pytest.mark.asyncio
async def test_flush_method():
    event = PhoneCallEndedEvent(conversation_id=CONVERSATION_ID, type=EventType.PHONE_CALL_ENDED)
    manager = EventsManager([EventType.PHONE_CALL_ENDED])
    for _ in range(5):
        manager.publish_event(event)
    await manager.flush()
    assert manager.queue.empty()


@pytest.mark.asyncio
async def test_queue_empty_and_timeout():
    manager = EventsManager([EventType.TRANSCRIPT])
    await manager.flush()
    assert manager.queue.empty()
