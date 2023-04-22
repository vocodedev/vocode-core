from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, validator
from vocode.streaming.models.client_backend import OutputAudioConfig

from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.telephony.constants import (
    DEFAULT_AUDIO_ENCODING,
    DEFAULT_SAMPLING_RATE,
)
from .model import TypedModel
from .audio_encoding import AudioEncoding


class SynthesizerType(str, Enum):
    BASE = "synthesizer_base"
    AZURE = "synthesizer_azure"
    GOOGLE = "synthesizer_google"
    ELEVEN_LABS = "synthesizer_eleven_labs"
    RIME = "synthesizer_rime"
    PLAY_HT = "synthesizer_play_ht"
    GTTS = "synthesizer_gtts"
    STREAM_ELEMENTS = "synthesizer_stream_elements"


class SentimentConfig(BaseModel):
    emotions: List[str] = ["angry", "friendly", "sad", "whispering"]

    @validator("emotions")
    def emotions_must_not_be_empty(cls, v):
        if len(v) == 0:
            raise ValueError("must have at least one emotion")
        return v


class SynthesizerConfig(TypedModel, type=SynthesizerType.BASE.value):
    sampling_rate: int
    audio_encoding: AudioEncoding
    should_encode_as_wav: bool = False
    sentiment_config: Optional[SentimentConfig] = None

    @classmethod
    def from_output_device(cls, output_device: BaseOutputDevice, **kwargs):
        return cls(
            sampling_rate=output_device.sampling_rate,
            audio_encoding=output_device.audio_encoding,
            **kwargs
        )

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


AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME = "en-US-AriaNeural"
AZURE_SYNTHESIZER_DEFAULT_PITCH = 0
AZURE_SYNTHESIZER_DEFAULT_RATE = 15


class AzureSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.AZURE.value):
    voice_name: str = AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME
    pitch: int = AZURE_SYNTHESIZER_DEFAULT_PITCH
    rate: int = AZURE_SYNTHESIZER_DEFAULT_RATE


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


class ElevenLabsSynthesizerConfig(
    SynthesizerConfig, type=SynthesizerType.ELEVEN_LABS.value
):
    api_key: Optional[str] = None
    voice_id: Optional[str] = ELEVEN_LABS_ADAM_VOICE_ID
    stability: Optional[float]
    similarity_boost: Optional[float]

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


class RimeSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.RIME.value):
    speaker: str


class PlayHtSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.PLAY_HT.value):
    voice_id: str
    speed: Optional[str] = None
    preset: Optional[str] = None


class GTTSSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.GTTS.value):
    pass


STREAM_ELEMENTS_SYNTHESIZER_DEFAULT_VOICE = "Brian"


class StreamElementsSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.STREAM_ELEMENTS.value):
    voice: str = STREAM_ELEMENTS_SYNTHESIZER_DEFAULT_VOICE
