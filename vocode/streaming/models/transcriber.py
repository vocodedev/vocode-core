from enum import Enum
from typing import Optional

from vocode.streaming.input_device.base_input_device import BaseInputDevice
from vocode.streaming.telephony.constants import (
    DEFAULT_AUDIO_ENCODING,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_SAMPLING_RATE,
)
from .audio_encoding import AudioEncoding
from .model import BaseModel, TypedModel


class TranscriberType(str, Enum):
    BASE = "transcriber_base"
    DEEPGRAM = "transcriber_deepgram"
    GOOGLE = "transcriber_google"
    ASSEMBLY_AI = "transcriber_assembly_ai"


class EndpointingType(str, Enum):
    BASE = "endpointing_base"
    TIME_BASED = "endpointing_time_based"
    PUNCTUATION_BASED = "endpointing_punctuation_based"


class EndpointingConfig(TypedModel, type=EndpointingType.BASE):
    pass


class TimeEndpointingConfig(EndpointingConfig, type=EndpointingType.TIME_BASED):
    time_cutoff_seconds: float = 0.4


class PunctuationEndpointingConfig(
    EndpointingConfig, type=EndpointingType.PUNCTUATION_BASED
):
    time_cutoff_seconds: float = 0.4


class TranscriberConfig(TypedModel, type=TranscriberType.BASE):
    sampling_rate: int
    audio_encoding: AudioEncoding
    chunk_size: int
    endpointing_config: Optional[EndpointingConfig] = None

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


class DeepgramTranscriberConfig(TranscriberConfig, type=TranscriberType.DEEPGRAM):
    language: Optional[str] = None
    model: Optional[str] = None
    tier: Optional[str] = None
    should_warmup_model: bool = False
    version: Optional[str] = None
    downsampling: Optional[int] = None


class GoogleTranscriberConfig(TranscriberConfig, type=TranscriberType.GOOGLE):
    model: Optional[str] = None
    should_warmup_model: bool = False


class AssemblyAITranscriberConfig(TranscriberConfig, type=TranscriberType.ASSEMBLY_AI):
    should_warmup_model: bool = False
