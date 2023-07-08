import asyncio
import logging
import pytest
from tests.streaming.fixtures.output_device import SilentOutputDevice
from tests.streaming.fixtures.synthesizer import TestSynthesizer, TestSynthesizerConfig
from tests.streaming.fixtures.transcriber import (
    TestAsyncTranscriber,
    TestTranscriberConfig,
)
from vocode.streaming.agent.echo_agent import EchoAgent
from vocode.streaming.models.agent import EchoAgentConfig
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.streaming_conversation import StreamingConversation

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@pytest.mark.asyncio
async def test_streaming_conversation():
    sampling_rate = 16000
    audio_encoding = AudioEncoding.LINEAR16
    chunk_size = 2048
    silent_output_device = SilentOutputDevice(
        sampling_rate=sampling_rate, audio_encoding=audio_encoding
    )

    conversation = StreamingConversation(
        output_device=silent_output_device,
        transcriber=TestAsyncTranscriber(
            TestTranscriberConfig(
                sampling_rate=sampling_rate,
                audio_encoding=audio_encoding,
                chunk_size=chunk_size,
            )
        ),
        agent=EchoAgent(
            EchoAgentConfig(
                initial_message=BaseMessage(text="test"),
            )
        ),
        synthesizer=TestSynthesizer(
            TestSynthesizerConfig.from_output_device(silent_output_device)
        ),
        logger=logger,
    )
    await conversation.start()
    await asyncio.sleep(1)
    await conversation.terminate()
