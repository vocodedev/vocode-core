import pytest
from vocode.streaming.synthesizer.base_synthesizer import SynthesisResult
from vocode.streaming.synthesizer.eleven_labs_synthesizer import (
    ElevenLabsSynthesizer,
    ELEVEN_LABS_BASE_URL,
)
from aioresponses import aioresponses
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from vocode.streaming.models.message import BaseMessage
import re

@pytest.mark.asyncio
async def test_eleven_labs(client_eleven_labs_synthesizer: ElevenLabsSynthesizer, mock_eleven_labs_api: aioresponses):
    response = await client_eleven_labs_synthesizer.create_speech(BaseMessage(text="Hello, world!"), 1024)
    print("response")
    print(response)
    # assert(isinstance(response, SynthesisResult))
    