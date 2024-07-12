import asyncio

import pytest
from fastapi import WebSocket
from pytest_mock import MockerFixture

from tests.fakedata.conversation import (
    create_fake_streaming_conversation_factory,
    create_fake_vonage_phone_conversation_with_streaming_conversation_pipeline,
)
from tests.fixtures.synthesizer import TestSynthesizer, TestSynthesizerConfig
from tests.fixtures.transcriber import TestAsyncTranscriber, TestTranscriberConfig
from vocode.streaming.agent.echo_agent import EchoAgent
from vocode.streaming.models.agent import EchoAgentConfig
from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.telephony.constants import VONAGE_CHUNK_SIZE, VONAGE_SAMPLING_RATE


@pytest.mark.asyncio
async def test_vonage_phone_conversation_pipeline(
    mocker: MockerFixture,
    mock_ws: WebSocket,
    incoming_websocket_messages: asyncio.Queue,
    outgoing_websocket_messages: asyncio.Queue,
):

    vonage_phone_conversation = (
        create_fake_vonage_phone_conversation_with_streaming_conversation_pipeline(
            mocker,
            streaming_conversation_factory=create_fake_streaming_conversation_factory(
                mocker,
                transcriber=TestAsyncTranscriber(
                    TestTranscriberConfig(
                        sampling_rate=VONAGE_SAMPLING_RATE,
                        audio_encoding=AudioEncoding.LINEAR16,
                        chunk_size=VONAGE_CHUNK_SIZE,
                    )
                ),
                agent=EchoAgent(
                    EchoAgentConfig(initial_message=BaseMessage(text="Hi there")),
                ),
                synthesizer=TestSynthesizer(
                    TestSynthesizerConfig(
                        sampling_rate=VONAGE_SAMPLING_RATE, audio_encoding=AudioEncoding.LINEAR16
                    )
                ),
            ),
        )
    )

    handle_ws_messages_task = asyncio.create_task(
        vonage_phone_conversation.attach_ws_and_start(mock_ws)
    )
    incoming_websocket_messages.put_nowait({"type": "websocket.receive", "text": "START MESSAGE"})
    await vonage_phone_conversation.pipeline.initial_message_tracker.wait()
    bytes_ws_message = await outgoing_websocket_messages.get()
    assert bytes_ws_message["bytes"] == b"Hi there"

    incoming_websocket_messages.put_nowait({"type": "websocket.receive", "bytes": b"test"})

    bytes_ws_message = await outgoing_websocket_messages.get()
    assert bytes_ws_message["bytes"] == b"test"

    vonage_phone_conversation.pipeline.mark_terminated()

    # send a dummy message to make sure VonagePhoneConversation doesn't get hung on receive_text()
    incoming_websocket_messages.put_nowait({"type": "websocket.receive", "bytes": b"dummy"})

    await handle_ws_messages_task
    await handle_ws_messages_task
