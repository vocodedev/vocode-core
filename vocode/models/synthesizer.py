from enum import Enum
from .model import TypedModel
from .audio_encoding import AudioEncoding
from ..output_device.base_output_device import BaseOutputDevice

class SynthesizerType(str, Enum):
    BASE = "base"
    AZURE = "azure"
    GOOGLE = "google"
    ELEVEN_LABS = "eleven_labs"

class SynthesizerConfig(TypedModel, type=SynthesizerType.BASE):
    sampling_rate: int
    audio_encoding: AudioEncoding

    @classmethod
    def from_output_device(cls, output_device: BaseOutputDevice):
        return cls(sampling_rate=output_device.sampling_rate, audio_encoding=output_device.audio_encoding)

class AzureSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.AZURE):
    pass

class GoogleSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.GOOGLE):
    pass

class ElevenLabsSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.ELEVEN_LABS):
    pass
