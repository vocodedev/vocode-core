import asyncio
import base64
import json

import pytest
from fastapi import WebSocket
from pytest_mock import MockerFixture

from tests.fakedata.conversation import (
    create_fake_streaming_conversation_factory,
    create_fake_twilio_phone_conversation_with_streaming_conversation_pipeline,
)
from tests.fixtures.synthesizer import TestSynthesizer, TestSynthesizerConfig
from tests.fixtures.transcriber import TestAsyncTranscriber, TestTranscriberConfig
from vocode.streaming.agent.echo_agent import EchoAgent
from vocode.streaming.models.agent import EchoAgentConfig
from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.telephony.constants import DEFAULT_CHUNK_SIZE, DEFAULT_SAMPLING_RATE


@pytest.mark.asyncio
async def test_twilio_phone_conversation_pipeline(
    mocker: MockerFixture,
    mock_ws: WebSocket,
    incoming_websocket_messages: asyncio.Queue,
    outgoing_websocket_messages: asyncio.Queue,
):

    twilio_phone_conversation = (
        create_fake_twilio_phone_conversation_with_streaming_conversation_pipeline(
            mocker,
            streaming_conversation_factory=create_fake_streaming_conversation_factory(
                mocker,
                transcriber=TestAsyncTranscriber(
                    TestTranscriberConfig(
                        sampling_rate=DEFAULT_SAMPLING_RATE,
                        audio_encoding=AudioEncoding.MULAW,
                        chunk_size=DEFAULT_CHUNK_SIZE,
                    )
                ),
                agent=EchoAgent(
                    EchoAgentConfig(initial_message=BaseMessage(text="Hi there")),
                ),
                synthesizer=TestSynthesizer(
                    TestSynthesizerConfig(
                        sampling_rate=DEFAULT_SAMPLING_RATE, audio_encoding=AudioEncoding.MULAW
                    )
                ),
            ),
        )
    )

    stream_sid = "twilio_stream_sid"

    incoming_websocket_messages.put_nowait(
        {
            "type": "websocket.receive",
            "text": json.dumps({"event": "start", "start": {"streamSid": stream_sid}}),
        },  # twilio start
    )

    handle_ws_messages_task = asyncio.create_task(
        twilio_phone_conversation.attach_ws_and_start(mock_ws)
    )
    incoming_websocket_messages.put_nowait(
        {
            "type": "websocket.receive",
            "text": json.dumps({"event": "mark", "mark": {"name": "mark_1"}}),
        },  # twilio mark for the initial message
    )
    await twilio_phone_conversation.pipeline.initial_message_tracker.wait()
    media_message = (await outgoing_websocket_messages.get())["text"]
    assert media_message == json.dumps(
        {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": base64.b64encode(b"Hi there").decode("utf-8"),
            },
        }
    )
    mark_message = (await outgoing_websocket_messages.get())["text"]
    assert json.loads(mark_message)["event"] == "mark"

    incoming_websocket_messages.put_nowait(
        {
            "type": "websocket.receive",
            "text": json.dumps(
                {"event": "media", "media": {"payload": base64.b64encode(b"test").decode("utf-8")}}
            ),
        }
    )

    # TODO (vocode 0.2.0): see if it's necessary to broadcast interrupt initially
    clear_message = (await outgoing_websocket_messages.get())["text"]
    assert json.loads(clear_message)["event"] == "clear"

    media_message = (await outgoing_websocket_messages.get())["text"]
    assert media_message == json.dumps(
        {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": base64.b64encode(b"test").decode("utf-8"),
            },
        }
    )
    mark_message = (await outgoing_websocket_messages.get())["text"]
    assert json.loads(mark_message)["event"] == "mark"

    twilio_phone_conversation.pipeline.mark_terminated()

    # send a dummy message to make sure TwilioPhoneConversation doesn't get hung on receive_text()
    incoming_websocket_messages.put_nowait(
        {
            "type": "websocket.receive",
            "text": json.dumps(
                {"event": "media", "media": {"payload": base64.b64encode(b"dummy").decode("utf-8")}}
            ),
        }
    )

    await handle_ws_messages_task
