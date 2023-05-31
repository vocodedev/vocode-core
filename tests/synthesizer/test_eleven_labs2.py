import unittest
from unittest.mock import patch
from aioresponses import aioresponses
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from vocode.streaming.synthesizer.eleven_labs_synthesizer import (
    ElevenLabsSynthesizer,
    ELEVEN_LABS_BASE_URL,
)
from vocode.streaming.synthesizer.base_synthesizer import SynthesisResult
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.audio_encoding import AudioEncoding
import re

class TestElevenLabsSynthesizer(unittest.TestCase):
    @aioresponses()
    def test_create_speech(self, m):
        # Assuming you have some test data...
        test_message = BaseMessage(text="Hello, world!")
        test_chunk_size = 100
        sampling_rate = 16000
        audio_encoding = AudioEncoding.LINEAR16

        # Mock the HTTP response from the ElevenLabs API
        pattern = re.compile(rf"{re.escape(ELEVEN_LABS_BASE_URL)}text-to-speech/\w+")
        m.post(pattern, status=200, payload=b'fake_audio_data')

        # Create an instance of your synthesizer
        synthesizer_config = ElevenLabsSynthesizerConfig(api_key='my_api_key', sampling_rate=sampling_rate, audio_encoding=audio_encoding)
        synthesizer = ElevenLabsSynthesizer(synthesizer_config)

        # Call your method and assert the returned data
        result = synthesizer.create_speech(test_message, test_chunk_size)
        self.assertIsInstance(result, SynthesisResult)
        self.assertTrue(any(chunk for chunk in result.chunk_generator))

    # More tests...

if __name__ == "__main__":
    unittest.main()