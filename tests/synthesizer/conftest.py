import pytest
from aioresponses import aioresponses, CallbackResult
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
import re
from vocode.streaming.synthesizer.eleven_labs_synthesizer import (
    ElevenLabsSynthesizer,
    ELEVEN_LABS_BASE_URL,
)
import re
from tests.streaming.data.loader import get_audio_path

DEFAULT_PARAMS = {'sampling_rate': 16000, 'audio_encoding': AudioEncoding.LINEAR16}

def create_request_handler(optimize_streaming_latency=False):
    def request_handler(url, headers, **kwargs):
        if optimize_streaming_latency and "optimize_streaming_latency=1" not in str(url):
            raise Exception("optimize_streaming_latency=1 not found in url")
        if headers['xi-api-key'] != 'my_api_key':
            return CallbackResult(status=401)
        with open(get_audio_path("fake_audio.mp3"), 'rb') as audio_file:
            return CallbackResult(content_type='audio/mpeg', body=audio_file.read())
    return request_handler

@pytest.fixture
def mock_eleven_labs_api():
    with aioresponses() as m:
        pattern = re.compile(rf"{re.escape(ELEVEN_LABS_BASE_URL)}text-to-speech/\w+")
        m.post(pattern, callback=create_request_handler())
        yield m

@pytest.fixture
def mock_eleven_labs_api_optimize_streaming_latency():
    with aioresponses() as m:
        pattern = re.compile(rf"{re.escape(ELEVEN_LABS_BASE_URL)}text-to-speech/\w+")
        m.post(pattern, callback=create_request_handler(optimize_streaming_latency=True))
        yield m
    
        
@pytest.fixture(scope="module")
def eleven_labs_synthesizer_with_api_key():
    params = DEFAULT_PARAMS.copy()
    params["api_key"] = "my_api_key"
    yield ElevenLabsSynthesizer(ElevenLabsSynthesizerConfig(**params))
    
@pytest.fixture(scope="module")
def eleven_labs_synthesizer_wrong_api_key():
    params = DEFAULT_PARAMS.copy()
    params["api_key"] = "wrong_api_key"
    yield ElevenLabsSynthesizer(ElevenLabsSynthesizerConfig(**params))

@pytest.fixture(scope="module")
def eleven_labs_synthesizer_env_api_key():
    params = DEFAULT_PARAMS.copy()
    import os
    os.environ['ELEVEN_LABS_API_KEY'] = 'my_api_key'
    yield ElevenLabsSynthesizer(ElevenLabsSynthesizerConfig(**params))
    
@pytest.fixture(scope="module")
def eleven_labs_synthesizer_stability_similarity():
    params = DEFAULT_PARAMS.copy()
    params["stability"] = 0.5
    params["similarity_boost"] = 0.5
    yield ElevenLabsSynthesizer(ElevenLabsSynthesizerConfig(**params))
    
@pytest.fixture(scope="module")
def eleven_labs_synthesizer_optimize_streaming_latency():
    params = DEFAULT_PARAMS.copy()
    params["optimize_streaming_latency"] = 1
    yield ElevenLabsSynthesizer(ElevenLabsSynthesizerConfig(**params))
    
@pytest.fixture(scope="module")
def eleven_labs_synthesizer_voice_id():
    params = DEFAULT_PARAMS.copy()
    from vocode.streaming.synthesizer.eleven_labs_synthesizer import ADAM_VOICE_ID
    params["voice_id"] = ADAM_VOICE_ID
    yield ElevenLabsSynthesizer(ElevenLabsSynthesizerConfig(**params))
    
@pytest.fixture(scope="module")
def eleven_labs_synthesizer_only_stability():
    params = DEFAULT_PARAMS.copy()
    params["stability"] = 0.5
    yield ElevenLabsSynthesizer(ElevenLabsSynthesizerConfig(**params))