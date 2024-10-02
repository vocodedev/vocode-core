from abc import ABC
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, field_validator, model_validator
from pydantic.v1 import validator

from vocode.streaming.models.adaptive_object import AdaptiveObject
from vocode.streaming.models.client_backend import OutputAudioConfig
from vocode.streaming.output_device.abstract_output_device import AbstractOutputDevice
from vocode.streaming.telephony.constants import DEFAULT_AUDIO_ENCODING, DEFAULT_SAMPLING_RATE

from .audio import AudioEncoding, SamplingRate


class SentimentConfig(BaseModel):
    emotions: List[str] = ["angry", "friendly", "sad", "whispering"]

    @validator("emotions")
    def emotions_must_not_be_empty(cls, v):
        if len(v) == 0:
            raise ValueError("must have at least one emotion")
        return v


class SynthesizerConfig(AdaptiveObject, ABC):
    type: Any
    sampling_rate: int
    audio_encoding: AudioEncoding
    should_encode_as_wav: bool = False
    sentiment_config: Optional[SentimentConfig] = None

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_output_device(cls, output_device: AbstractOutputDevice, **kwargs):
        return cls(
            sampling_rate=output_device.sampling_rate,
            audio_encoding=output_device.audio_encoding,
            **kwargs
        )

    # TODO(EPD-186): switch to from_twilio_output_device and from_vonage_output_device
    @classmethod
    def from_telephone_output_device(cls, **kwargs):
        return cls(
            sampling_rate=DEFAULT_SAMPLING_RATE, audio_encoding=DEFAULT_AUDIO_ENCODING, **kwargs
        )

    @classmethod
    def from_output_audio_config(cls, output_audio_config: OutputAudioConfig, **kwargs):
        return cls(
            sampling_rate=output_audio_config.sampling_rate,
            audio_encoding=output_audio_config.audio_encoding,
            **kwargs
        )


AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME = "en-US-SteffanNeural"
AZURE_SYNTHESIZER_DEFAULT_PITCH = 0
AZURE_SYNTHESIZER_DEFAULT_RATE = 15


class AzureSynthesizerConfig(SynthesizerConfig):
    type: Literal["synthesizer_azure"] = "synthesizer_azure"
    voice_name: str = AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME
    pitch: int = AZURE_SYNTHESIZER_DEFAULT_PITCH
    rate: int = AZURE_SYNTHESIZER_DEFAULT_RATE
    language_code: str = "en-US"


DEFAULT_GOOGLE_LANGUAGE_CODE = "en-US"
DEFAULT_GOOGLE_VOICE_NAME = "en-US-Neural2-I"
DEFAULT_GOOGLE_PITCH = 0
DEFAULT_GOOGLE_SPEAKING_RATE = 1.2


class GoogleSynthesizerConfig(SynthesizerConfig):
    type: Literal["synthesizer_google"] = "synthesizer_google"
    language_code: str = DEFAULT_GOOGLE_LANGUAGE_CODE
    voice_name: str = DEFAULT_GOOGLE_VOICE_NAME
    pitch: float = DEFAULT_GOOGLE_PITCH
    speaking_rate: float = DEFAULT_GOOGLE_SPEAKING_RATE


ELEVEN_LABS_ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"


class ElevenLabsSynthesizerConfig(SynthesizerConfig):
    type: Literal["synthesizer_eleven_labs"] = "synthesizer_eleven_labs"
    api_key: Optional[str] = None
    voice_id: Optional[str] = ELEVEN_LABS_ADAM_VOICE_ID
    optimize_streaming_latency: Optional[int]
    experimental_streaming: bool = False
    stability: Optional[float]
    similarity_boost: Optional[float]
    model_id: Optional[str]
    experimental_websocket: bool = False
    backchannel_amplitude_factor: float = 0.5

    @field_validator("voice_id", mode="after")
    @classmethod
    def set_name(cls, voice_id):
        return voice_id or ELEVEN_LABS_ADAM_VOICE_ID

    @model_validator(mode="after")
    def stability_and_similarity_boost_check(self):
        if (self.stability is None) != (self.similarity_boost is None):
            raise ValueError("Both stability and similarity_boost must be set or not set.")
        return self

    @field_validator("optimize_streaming_latency", mode="after")
    @classmethod
    def optimize_streaming_latency_check(cls, optimize_streaming_latency):
        if optimize_streaming_latency is not None and not (0 <= optimize_streaming_latency <= 4):
            raise ValueError("optimize_streaming_latency must be between 0 and 4.")
        return optimize_streaming_latency

    @field_validator("backchannel_amplitude_factor", mode="after")
    @classmethod
    def backchannel_amplitude_factor_check(cls, backchannel_amplitude_factor):
        if backchannel_amplitude_factor is not None and not (0 < backchannel_amplitude_factor <= 1):
            raise ValueError(
                "backchannel_amplitude_factor must be between 0 (not inclusive) and 1."
            )
        return backchannel_amplitude_factor


RIME_DEFAULT_BASE_URL = "https://users.rime.ai/v1/rime-tts"
RIME_DEFAULT_MODEL_ID = None
RIME_DEFAULT_SPEAKER = "young_male_unmarked-1"
RIME_DEFAULT_SPEED_ALPHA = 1.0
RIME_DEFAULT_SAMPLE_RATE = SamplingRate.RATE_22050
RIME_DEFAULT_REDUCE_LATENCY = False
RimeModelId = Literal["mist", "v1"]


class RimeSynthesizerConfig(SynthesizerConfig):
    type: Literal["synthesizer_rime"] = "synthesizer_rime"
    base_url: str = RIME_DEFAULT_BASE_URL
    model_id: Optional[Literal[RimeModelId]] = RIME_DEFAULT_MODEL_ID
    speaker: str = RIME_DEFAULT_SPEAKER
    speed_alpha: Optional[float] = RIME_DEFAULT_SPEED_ALPHA
    sampling_rate: int = RIME_DEFAULT_SAMPLE_RATE
    reduce_latency: Optional[bool] = RIME_DEFAULT_REDUCE_LATENCY


PlayHtVoiceVersionType = Literal["1", "2"]


class PlayHtSynthesizerConfig(SynthesizerConfig):
    type: Literal["synthesizer_play_ht"] = "synthesizer_play_ht"
    voice_id: str
    api_key: Optional[str] = None
    user_id: Optional[str] = None
    speed: Optional[float] = None
    seed: Optional[int] = None
    temperature: Optional[float] = None
    quality: Optional[str] = None
    experimental_streaming: bool = False
    version: Literal[PlayHtVoiceVersionType] = "2"
    top_p: Optional[float] = None
    text_guidance: Optional[float] = None
    voice_guidance: Optional[float] = None
    on_prem: bool = False
    on_prem_provider: Literal["aws", "gcp"] = "gcp"
    experimental_remove_silence: bool = False


class CoquiTTSSynthesizerConfig(SynthesizerConfig):
    type: Literal["synthesizer_coqui_tts"] = "synthesizer_coqui_tts"
    tts_kwargs: dict = {}
    speaker: Optional[str] = None
    language: Optional[str] = None


class GTTSSynthesizerConfig(SynthesizerConfig):
    type: Literal["synthesizer_gtts"] = "synthesizer_gtts"


STREAM_ELEMENTS_SYNTHESIZER_DEFAULT_VOICE = "Brian"


class StreamElementsSynthesizerConfig(SynthesizerConfig):
    type: Literal["synthesizer_stream_elements"] = "synthesizer_stream_elements"
    voice: str = STREAM_ELEMENTS_SYNTHESIZER_DEFAULT_VOICE


class BarkSynthesizerConfig(SynthesizerConfig):
    type: Literal["synthesizer_bark"] = "synthesizer_bark"
    preload_kwargs: Dict[str, Any] = {}
    generate_kwargs: Dict[str, Any] = {}


DEFAULT_POLLY_LANGUAGE_CODE = "en-US"
DEFAULT_POLLY_VOICE_ID = "Matthew"
DEFAULT_POLLY_SAMPLING_RATE = SamplingRate.RATE_16000.value


class PollySynthesizerConfig(SynthesizerConfig):
    type: Literal["synthesizer_polly"] = "synthesizer_polly"
    language_code: str = DEFAULT_POLLY_LANGUAGE_CODE
    voice_id: str = DEFAULT_POLLY_VOICE_ID
    sampling_rate: int = DEFAULT_POLLY_SAMPLING_RATE


DEFAULT_CARTESIA_MODEL_ID = "sonic-english"
DEFAULT_CARTESIA_VOICE_ID = "f9836c6e-a0bd-460e-9d3c-f7299fa60f94"


class CartesiaVoiceControls(BaseModel):
    """See https://docs.cartesia.ai/user-guides/voice-control"""

    speed: Optional[Union[float, str]] = None
    emotion: Optional[List[str]] = None


class CartesiaSynthesizerConfig(SynthesizerConfig):
    type: Literal["synthesizer_cartesia"] = "synthesizer_cartesia"
    api_key: Optional[str] = None
    model_id: str = DEFAULT_CARTESIA_MODEL_ID
    voice_id: str = DEFAULT_CARTESIA_VOICE_ID
    experimental_voice_controls: Optional[CartesiaVoiceControls] = None
