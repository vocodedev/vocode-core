from enum import Enum
from typing import Optional
from .model import TypedModel
from .audio_encoding import AudioEncoding
from ..output_device.base_output_device import BaseOutputDevice

class SynthesizerType(str, Enum):
    BASE = "synthesizer_base"
    AZURE = "synthesizer_azure"
    GOOGLE = "synthesizer_google"
    ELEVEN_LABS = "synthesizer_eleven_labs"

class SynthesizerConfig(TypedModel, type=SynthesizerType.BASE):
    sampling_rate: int
    audio_encoding: AudioEncoding

    @classmethod
    def from_output_device(cls, output_device: BaseOutputDevice):
        return cls(sampling_rate=output_device.sampling_rate, audio_encoding=output_device.audio_encoding)

class AzureSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.AZURE):
    voice_name: Optional[str] = None
    pitch: Optional[int] = None
    rate: Optional[int] = None

    @classmethod
    def from_output_device(
        cls, 
        output_device: BaseOutputDevice, 
        voice_name: Optional[str] = None,
        pitch: Optional[int] = None,
        rate: Optional[int] = None,
    ):
        return cls(
            sampling_rate=output_device.sampling_rate, 
            audio_encoding=output_device.audio_encoding,
            voice_name=voice_name,
            pitch=pitch,
            rate=rate,
        )
    pass

class GoogleSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.GOOGLE):
    pass
