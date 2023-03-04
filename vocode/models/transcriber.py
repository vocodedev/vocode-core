from enum import Enum
from typing import Optional
from .audio_encoding import AudioEncoding
from .model import BaseModel, TypedModel
from ..input_device.base_input_device import BaseInputDevice


class TranscriberType(str, Enum):
    BASE = "transcriber_base"
    DEEPGRAM = "transcriber_deepgram"
    GOOGLE = "transcriber_google"
    ASSEMBLY_AI = "transcriber_assembly_ai"


class EndpointingConfig(BaseModel):
    time_cutoff_seconds: Optional[float] = None


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
    ):
        return cls(
            sampling_rate=input_device.sampling_rate,
            audio_encoding=input_device.audio_encoding,
            chunk_size=input_device.chunk_size,
            endpointing_config=endpointing_config,
        )


class DeepgramTranscriberConfig(TranscriberConfig, type=TranscriberType.DEEPGRAM):
    model: Optional[str] = None
    should_warmup_model: bool = False
    version: Optional[str] = None


class GoogleTranscriberConfig(TranscriberConfig, type=TranscriberType.GOOGLE):
    model: Optional[str] = None
    should_warmup_model: bool = False


class AssemblyAITranscriberConfig(TranscriberConfig, type=TranscriberType.ASSEMBLY_AI):
    should_warmup_model: bool = False
