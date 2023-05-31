import pytest
from aioresponses import aioresponses
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
import re
from vocode.streaming.synthesizer.eleven_labs_synthesizer import (
    ElevenLabsSynthesizer,
    ELEVEN_LABS_BASE_URL,
)
# from tests.synthesizer.data.loader import get_audio_path

@pytest.fixture
def mock_eleven_labs_api():
    with aioresponses() as m:
        pattern = re.compile(rf"{re.escape(ELEVEN_LABS_BASE_URL)}text-to-speech/\w+")
        with open("./data/fake_audio.mp3", 'rb') as audio_file: #TODO: replace with get_audio_path
            m.post(pattern, content_type='audio/mpeg', body=audio_file.read())
        yield m
        
@pytest.fixture(scope="module")
def eleven_labs_config():
    from vocode.streaming.models.audio_encoding import AudioEncoding
    from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
    sampling_rate = 16000
    audio_encoding = AudioEncoding.LINEAR16
    yield ElevenLabsSynthesizerConfig(api_key='my_api_key', sampling_rate=sampling_rate, audio_encoding=audio_encoding, stability=0.5, similarity_boost=0.5, optimize_streaming_latency=True, model_id='my_model_id')
    
@pytest.fixture(scope="module")
def client_eleven_labs_synthesizer(eleven_labs_config: ElevenLabsSynthesizerConfig):
    yield ElevenLabsSynthesizer(eleven_labs_config)
