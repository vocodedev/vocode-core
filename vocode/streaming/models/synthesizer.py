from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, validator
from .model import TypedModel
from .audio_encoding import AudioEncoding
from ..output_device.base_output_device import BaseOutputDevice


class SynthesizerType(str, Enum):
    BASE = "synthesizer_base"
    AZURE = "synthesizer_azure"
    GOOGLE = "synthesizer_google"
    ELEVEN_LABS = "synthesizer_eleven_labs"
    RIME = "synthesizer_rime"


class TrackBotSentimentConfig(BaseModel):
    emotions: list[str] = ["angry", "friendly", "sad", "whispering"]

    @validator("emotions")
    def emotions_must_not_be_empty(cls, v):
        if len(v) == 0:
            raise ValueError("must have at least one emotion")
        return v


class SynthesizerConfig(TypedModel, type=SynthesizerType.BASE):
    sampling_rate: int
    audio_encoding: AudioEncoding
    should_encode_as_wav: bool = False
    track_bot_sentiment_in_voice: Union[bool, TrackBotSentimentConfig] = False

    @classmethod
    def from_output_device(cls, output_device: BaseOutputDevice):
        return cls(
            sampling_rate=output_device.sampling_rate,
            audio_encoding=output_device.audio_encoding,
        )


AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME = "en-US-AriaNeural"
AZURE_SYNTHESIZER_DEFAULT_PITCH = 0
AZURE_SYNTHESIZER_DEFAULT_RATE = 15


class AzureSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.AZURE):
    voice_name: str = AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME
    pitch: int = AZURE_SYNTHESIZER_DEFAULT_PITCH
    rate: int = AZURE_SYNTHESIZER_DEFAULT_RATE

    @classmethod
    def from_output_device(
        cls,
        output_device: BaseOutputDevice,
        voice_name: str = AZURE_SYNTHESIZER_DEFAULT_VOICE_NAME,
        pitch: int = AZURE_SYNTHESIZER_DEFAULT_PITCH,
        rate: int = AZURE_SYNTHESIZER_DEFAULT_RATE,
        track_bot_sentiment_in_voice: Union[bool, TrackBotSentimentConfig] = False,
    ):
        return cls(
            sampling_rate=output_device.sampling_rate,
            audio_encoding=output_device.audio_encoding,
            voice_name=voice_name,
            pitch=pitch,
            rate=rate,
            track_bot_sentiment_in_voice=track_bot_sentiment_in_voice,
        )

    pass


class GoogleSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.GOOGLE):
    pass


class RimeSynthesizerConfig(SynthesizerConfig, type=SynthesizerType.RIME):
    speaker: str

    @classmethod
    def from_output_device(
        cls,
        output_device: BaseOutputDevice,
        speaker: str,
    ):
        return cls(
            sampling_rate=output_device.sampling_rate,
            audio_encoding=output_device.audio_encoding,
            speaker=speaker,
        )
