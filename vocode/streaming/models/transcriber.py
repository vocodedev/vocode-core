from abc import ABC
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, field_validator

import vocode.streaming.livekit.constants as LiveKitConstants
from vocode.streaming.input_device.base_input_device import BaseInputDevice
from vocode.streaming.models.adaptive_object import AdaptiveObject
from vocode.streaming.models.client_backend import InputAudioConfig
from vocode.streaming.telephony.constants import (
    DEFAULT_AUDIO_ENCODING,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_SAMPLING_RATE,
)

from .audio import AudioEncoding

AZURE_DEFAULT_LANGUAGE = "en-US"
DEEPGRAM_API_WS_URL = "wss://api.deepgram.com"


class EndpointingConfig(AdaptiveObject, ABC):
    type: Any


class TimeEndpointingConfig(EndpointingConfig):
    type: Literal["endpointing_time_based"] = "endpointing_time_based"
    time_cutoff_seconds: float = 0.4


class PunctuationEndpointingConfig(EndpointingConfig):
    type: Literal["endpointing_punctuation_based"] = "endpointing_punctuation_based"
    time_cutoff_seconds: float = 0.4


class TranscriberConfig(AdaptiveObject, ABC):
    type: Any
    sampling_rate: int
    audio_encoding: AudioEncoding
    chunk_size: int
    endpointing_config: Optional[EndpointingConfig] = None
    downsampling: Optional[int] = None
    min_interrupt_confidence: Optional[float] = None
    mute_during_speech: bool = False

    @field_validator("min_interrupt_confidence", mode="after")
    @classmethod
    def min_interrupt_confidence_must_be_between_0_and_1(cls, v):
        if v is not None and (v < 0 or v > 1):
            raise ValueError("must be between 0 and 1")
        return v

    @classmethod
    def from_input_device(
        cls,
        input_device: BaseInputDevice,
        endpointing_config: Optional[EndpointingConfig] = None,
        **kwargs,
    ):
        return cls(
            sampling_rate=input_device.sampling_rate,
            audio_encoding=input_device.audio_encoding,
            chunk_size=input_device.chunk_size,
            endpointing_config=endpointing_config,
            **kwargs,
        )

    # TODO(EPD-186): switch to from_twilio_input_device and from_vonage_input_device
    @classmethod
    def from_telephone_input_device(
        cls,
        endpointing_config: Optional[EndpointingConfig] = None,
        **kwargs,
    ):
        return cls(
            sampling_rate=DEFAULT_SAMPLING_RATE,
            audio_encoding=DEFAULT_AUDIO_ENCODING,
            chunk_size=DEFAULT_CHUNK_SIZE,
            endpointing_config=endpointing_config,
            **kwargs,
        )

    @classmethod
    def from_input_audio_config(cls, input_audio_config: InputAudioConfig, **kwargs):
        return cls(
            sampling_rate=input_audio_config.sampling_rate,
            audio_encoding=input_audio_config.audio_encoding,
            chunk_size=input_audio_config.chunk_size,
            downsampling=input_audio_config.downsampling,
            **kwargs,
        )

    @classmethod
    def from_livekit_input_device(cls, **kwargs):
        return cls(
            sampling_rate=LiveKitConstants.DEFAULT_SAMPLING_RATE,
            audio_encoding=LiveKitConstants.AUDIO_ENCODING,
            chunk_size=LiveKitConstants.DEFAULT_CHUNK_SIZE,
            **kwargs,
        )


class DeepgramTranscriberConfig(TranscriberConfig):
    type: Literal["transcriber_deepgram"] = "transcriber_deepgram"
    language: Optional[str] = None
    model: Optional[str] = "nova"
    tier: Optional[str] = None
    version: Optional[str] = None
    keywords: Optional[list] = None
    api_key: Optional[str] = None
    on_prem: bool = False
    ws_url: str = DEEPGRAM_API_WS_URL


class GladiaTranscriberConfig(TranscriberConfig):
    type: Literal["transcriber_gladia"] = "transcriber_gladia"
    buffer_size_seconds: float = 0.1


class GoogleTranscriberConfig(TranscriberConfig):
    type: Literal["transcriber_google"] = "transcriber_google"
    model: Optional[str] = None
    language_code: str = "en-US"


class AzureTranscriberConfig(TranscriberConfig):
    type: Literal["transcriber_azure"] = "transcriber_azure"
    language: str = AZURE_DEFAULT_LANGUAGE
    candidate_languages: Optional[List[str]] = None


class AssemblyAITranscriberConfig(TranscriberConfig):
    type: Literal["transcriber_assembly_ai"] = "transcriber_assembly_ai"
    buffer_size_seconds: float = 0.1
    word_boost: Optional[List[str]] = None
    end_utterance_silence_threshold_milliseconds: Optional[int] = None


class WhisperCPPTranscriberConfig(TranscriberConfig):
    type: Literal["transcriber_whisper_cpp"] = "transcriber_whisper_cpp"
    buffer_size_seconds: float = 1
    libname: str
    fname_model: str


class RevAITranscriberConfig(TranscriberConfig):
    type: Literal["transcriber_rev_ai"] = "transcriber_rev_ai"


class Transcription(BaseModel):
    message: str
    confidence: float
    is_final: bool
    is_interrupt: bool = False
    bot_was_in_medias_res: bool = False
    duration_seconds: Optional[float] = None  # gets added only on final transcription

    def __str__(self):
        return (
            f"Transcription(message={self.message}, "
            + f"confidence={self.confidence}, "
            + f"is_final={self.is_final}, "
            + f"is_interrupt={self.is_interrupt}, "
            + f"bot_was_in_medias_res={self.bot_was_in_medias_res}, "
            + f"duration_seconds={self.duration_seconds}, "
            + f"wpm={self.wpm()}"
            + ")"
        )

    def wpm(self) -> Optional[float]:
        return (
            60 * len(self.message.split()) / self.duration_seconds
            if self.duration_seconds
            else None
        )
