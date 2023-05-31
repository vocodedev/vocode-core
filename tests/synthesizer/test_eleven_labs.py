import unittest
from unittest.mock import AsyncMock, patch
from pydub import AudioSegment
from vocode.streaming.synthesizer.eleven_labs_synthesizer import (
    ElevenLabsSynthesizer,
    ELEVEN_LABS_BASE_URL,
)
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.synthesizer.base_synthesizer import SynthesisResult
from aioresponses import aioresponses
import asyncio
import aiohttp
import re


class TestElevenLabsSynthesizer(unittest.IsolatedAsyncioTestCase):
    async def test_create_speech(self):
        # Create a mock response
        loop = asyncio.get_event_loop()
        session = aiohttp.ClientSession()

        # Patch the ClientSession object to return the mock session
        with aioresponses() as m:
            pattern = re.compile(ELEVEN_LABS_BASE_URL + "/.*")
            m.post(pattern, payload=dict(foo='bar'))
            # Create an instance of the ElevenLabsSynthesizer
            sampling_rate = 16000
            audio_encoding = AudioEncoding.LINEAR16
            synthesizerConfig = ElevenLabsSynthesizerConfig(api_key='my_api_key', sampling_rate=sampling_rate, audio_encoding=audio_encoding)
            synthesizer = ElevenLabsSynthesizer(synthesizerConfig)

            # Call the create_speech method
            result = synthesizer.create_speech(BaseMessage(text="Hello, world!"), 1024)
            self.assertTrue(isinstance(result, SynthesisResult))
            self.assertTrue(any(chunk for chunk in result.chunk_generator))

            # # Check that the request was made to the expected URL with the expected headers and body
            # mock_session.request.assert_called_once_with(
            #     "POST",
            #     ELEVEN_LABS_BASE_URL + "text-to-speech/pNInz6obpgDQGcFmaJgB",
            #     json={"text": "Hello, world!", "voice_settings": None},
            #     headers={"xi-api-key": None},
            # )