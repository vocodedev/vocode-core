import os
import __main__
import hashlib
from abc import abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import validator
from vocode.streaming.models.client_backend import OutputAudioConfig

from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.telephony.constants import (
    DEFAULT_AUDIO_ENCODING,
    DEFAULT_SAMPLING_RATE,
)

from vocode.streaming.models.index_config import IndexConfig
from vocode.streaming.models.model import BaseModel, TypedModel
from vocode.streaming.models.audio_encoding import AudioEncoding


DOCKER_CONTAINER = os.getenv("DOCKER_CONTAINER")
try:
    if DOCKER_CONTAINER:
        main_dir = "/code"
    else:
        main_dir = os.path.dirname(__main__.__file__)

    RANDOM_AUDIO_DIR = os.path.join(
        main_dir, "_submodules","vocode-python",
        "vocode", "streaming", "synthesizer"
    )

    FILLER_AUDIO_PATH = os.path.join(
        RANDOM_AUDIO_DIR,
        "filler_audio"
    )
    FOLLOW_UP_AUDIO_PATH = os.path.join(
        RANDOM_AUDIO_DIR,
        "follow_up_audio"
    )
    BACKTRACK_AUDIO_PATH = os.path.join(
        RANDOM_AUDIO_DIR,
        "backtrack_audio"
    )

    os.makedirs(FILLER_AUDIO_PATH, exist_ok=True)
    os.makedirs(FOLLOW_UP_AUDIO_PATH, exist_ok=True)
    os.makedirs(BACKTRACK_AUDIO_PATH, exist_ok=True)
except Exception as e:
    print(f"Error: {e}")
    FILLER_AUDIO_PATH = os.path.join(os.path.dirname(__file__), "filler_audio")
    FOLLOW_UP_AUDIO_PATH = os.path.join(os.path.dirname(__file__), "follow_up_audio")
    BACKTRACK_AUDIO_PATH = os.path.join(os.path.dirname(__file__), "backtrack_audio")


TYPING_NOISE_PATH = "%s/typing-noise.wav" % FILLER_AUDIO_PATH


def __hash__(instance) -> str:
    hash = hashlib.sha256()
    hash.update(bytes(getattr(instance, "type"), "utf-8"))
    for _, value in vars(instance).items():
        hash.update(bytes(str(value), "utf-8"))
    return hash.hexdigest()

class SynthesizerType(str, Enum):
    BASE = "synthesizer_base"
    AZURE = "synthesizer_azure"
    GOOGLE = "synthesizer_google"
    ELEVEN_LABS = "synthesizer_eleven_labs"
    RIME = "synthesizer_rime"
    PLAY_HT = "synthesizer_play_ht"
    GTTS = "synthesizer_gtts"
    STREAM_ELEMENTS = "synthesizer_stream_elements"
    COQUI_TTS = "synthesizer_coqui_tts"
    COQUI = "synthesizer_coqui"
    BARK = "synthesizer_bark"
    POLLY = "synthesizer_polly"


class SentimentConfig(BaseModel):
    emotions: List[str] = ["angry", "friendly", "sad", "whispering"]

    @validator("emotions")
    def emotions_must_not_be_empty(cls, v):
        if len(v) == 0:
            raise ValueError("must have at least one emotion")
        return v

# bluberry: copied from bot_sentiment_analyser.py 
class BotSentiment(BaseModel):
    emotion: Optional[str] = None
    degree: float = 0.0

class SynthesizerConfig(TypedModel, type=SynthesizerType.BASE.value):
    sampling_rate: int
    audio_encoding: AudioEncoding
    should_encode_as_wav: bool = False
    sentiment_config: Optional[SentimentConfig] = None
    initial_bot_sentiment: Optional[BotSentiment] = None
    index_config: Optional[IndexConfig] = None
    base_filler_audio_path: str = FILLER_AUDIO_PATH
    base_follow_up_audio_path: str = FOLLOW_UP_AUDIO_PATH
    base_backtrack_audio_path: str = BACKTRACK_AUDIO_PATH

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_output_device(cls, output_device: BaseOutputDevice, **kwargs):
        return cls(
            sampling_rate=output_device.sampling_rate,
            audio_encoding=output_device.audio_encoding,
            **kwargs
        )

    # TODO(EPD-186): switch to from_twilio_output_device and from_vonage_output_device
    @classmethod
    def from_telephone_output_device(cls, **kwargs):
        return cls(
            sampling_rate=DEFAULT_SAMPLING_RATE,
            audio_encoding=DEFAULT_AUDIO_ENCODING,
            **kwargs
        )

    @classmethod
    def from_output_audio_config(cls, output_audio_config: OutputAudioConfig, **kwargs):
        return cls(
            sampling_rate=output_audio_config.sampling_rate,
            audio_encoding=output_audio_config.audio_encoding,
            **kwargs
        )
    
    def __hash__(self) -> str:
        return __hash__(self)
    
    def get_cache_key(self, text: str) -> str:
        return self.__hash__() + text


AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME = "en-US-SteffanNeural"
AZURE_SYNTHESIZER_DEFAULT_PITCH = 0
AZURE_SYNTHESIZER_DEFAULT_RATE = 15


class AzureSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.AZURE.value):
    voice_name: str = AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME
    pitch: int = AZURE_SYNTHESIZER_DEFAULT_PITCH
    rate: int = AZURE_SYNTHESIZER_DEFAULT_RATE
    language_code: str = "en-US"    

    def get_cache_key(self, text: str) -> str:
        return f"{SynthesizerType.AZURE.value}:{self.voice_name}:{self.pitch}:{self.rate}:{text}"


DEFAULT_GOOGLE_LANGUAGE_CODE = "en-US"
DEFAULT_GOOGLE_VOICE_NAME = "en-US-Neural2-I"
DEFAULT_GOOGLE_PITCH = 0
DEFAULT_GOOGLE_SPEAKING_RATE = 1.2


class GoogleSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.GOOGLE.value):
    language_code: str = DEFAULT_GOOGLE_LANGUAGE_CODE
    voice_name: str = DEFAULT_GOOGLE_VOICE_NAME
    pitch: float = DEFAULT_GOOGLE_PITCH
    speaking_rate: float = DEFAULT_GOOGLE_SPEAKING_RATE


ELEVEN_LABS_ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVEN_LABS_CHARLIE_VOICE_ID = "IKne3meq5aSn9XLyUdCD"
ELEVEN_LABS_MYRA_VOICE_ID = "xiF4vIsZEX5eTp3pgNeH"


class ElevenLabsSynthesizerConfig(
    SynthesizerConfig, type=SynthesizerType.ELEVEN_LABS.value
):
    api_key: Optional[str] = None
    voice_id: Optional[str] = ELEVEN_LABS_CHARLIE_VOICE_ID
    optimize_streaming_latency: Optional[int]
    experimental_streaming: Optional[bool] = False
    stability: Optional[float]
    similarity_boost: Optional[float]
    model_id: Optional[str]
    use_cache: bool = True

    @validator("voice_id")
    def set_name(cls, voice_id):
        return voice_id or ELEVEN_LABS_ADAM_VOICE_ID

    @validator("similarity_boost", always=True)
    def stability_and_similarity_boost_check(cls, similarity_boost, values):
        stability = values.get("stability")
        if (stability is None) != (similarity_boost is None):
            raise ValueError(
                "Both stability and similarity_boost must be set or not set."
            )
        return similarity_boost

    @validator("optimize_streaming_latency")
    def optimize_streaming_latency_check(cls, optimize_streaming_latency):
        if optimize_streaming_latency is not None and not (
            0 <= optimize_streaming_latency <= 4
        ):
            raise ValueError("optimize_streaming_latency must be between 0 and 4.")
        return optimize_streaming_latency
    
    def get_cache_key(self, text: str) -> str:
        return f"{SynthesizerType.ELEVEN_LABS.value}:{self.model_id}:{self.voice_id}:{self.stability}:{self.similarity_boost}:{text}"


RIME_DEFAULT_SPEAKER = "young_male_unmarked-1"
RIME_DEFAULT_SAMPLE_RATE = 22050
RIME_DEFAULT_BASE_URL = "https://rjmopratfrdjgmfmaios.functions.supabase.co/rime-tts"


class RimeSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.RIME.value):
    speaker: str = RIME_DEFAULT_SPEAKER
    sampling_rate: int = RIME_DEFAULT_SAMPLE_RATE
    base_url: str = RIME_DEFAULT_BASE_URL
    speed_alpha: Optional[float] = None


COQUI_DEFAULT_SPEAKER_ID = "ebe2db86-62a6-49a1-907a-9a1360d4416e"


class CoquiSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.COQUI.value):
    api_key: Optional[str] = None
    voice_id: Optional[str] = COQUI_DEFAULT_SPEAKER_ID
    voice_prompt: Optional[str] = None
    use_xtts: Optional[bool] = True

    @validator("voice_id", always=True)
    def override_voice_id_with_prompt(cls, voice_id, values):
        if values.get("voice_prompt"):
            return None
        return voice_id or COQUI_DEFAULT_SPEAKER_ID


PLAYHT_DEFAULT_VOICE_ID = "larry"


class PlayHtSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.PLAY_HT.value):
    api_key: Optional[str] = None
    user_id: Optional[str] = None
    speed: Optional[int] = None
    seed: Optional[int] = None
    temperature: Optional[int] = None
    voice_id: str = PLAYHT_DEFAULT_VOICE_ID
    experimental_streaming: bool = False


class CoquiTTSSynthesizerConfig(
    SynthesizerConfig, type=SynthesizerType.COQUI_TTS.value
):
    tts_kwargs: dict = {}
    speaker: Optional[str] = None
    language: Optional[str] = None


class GTTSSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.GTTS.value):
    pass


STREAM_ELEMENTS_SYNTHESIZER_DEFAULT_VOICE = "Brian"


class StreamElementsSynthesizerConfig(
    SynthesizerConfig, type=SynthesizerType.STREAM_ELEMENTS.value
):
    voice: str = STREAM_ELEMENTS_SYNTHESIZER_DEFAULT_VOICE


class BarkSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.BARK.value):
    preload_kwargs: Dict[str, Any] = {}
    generate_kwargs: Dict[str, Any] = {}


DEFAULT_POLLY_LANGUAGE_CODE = "en-US"
DEFAULT_POLLY_VOICE_ID = "Matthew"
DEFAULT_POLLY_SAMPLING_RATE = 16000


class PollySynthesizerConfig(SynthesizerConfig, type=SynthesizerType.POLLY.value):
    language_code: str = DEFAULT_POLLY_LANGUAGE_CODE
    voice_id: str = DEFAULT_POLLY_VOICE_ID
    sampling_rate: int = DEFAULT_POLLY_SAMPLING_RATE
