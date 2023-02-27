from enum import Enum
from typing import Optional
from .audio_encoding import AudioEncoding
from .model import TypedModel
from ..input_device.base_input_device import BaseInputDevice

class TranscriberType(str, Enum):
    BASE = "base"
    DEEPGRAM = "deepgram"
    GOOGLE = "google"
    ASSEMBLY_AI = "assembly_ai"

class TranscriberConfig(TypedModel, type=TranscriberType.BASE):
    sampling_rate: int
    audio_encoding: AudioEncoding
    chunk_size: int

    @classmethod
    def from_input_device(cls, input_device: BaseInputDevice):
        return cls(
            sampling_rate=input_device.sampling_rate,
            audio_encoding=input_device.audio_encoding,
            chunk_size=input_device.chunk_size)

class DeepgramTranscriberConfig(TranscriberConfig, type=TranscriberType.DEEPGRAM):
    model: Optional[str] = None
    should_warmup_model: bool = False
    version: Optional[str] = None

class GoogleTranscriberConfig(TranscriberConfig, type=TranscriberType.GOOGLE):
    model: Optional[str] = None
    should_warmup_model: bool = False

class AssemblyAITranscriberConfig(TranscriberConfig, type=TranscriberType.ASSEMBLY_AI):
    should_warmup_model: bool = False