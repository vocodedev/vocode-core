from typing import Optional

from svara.streaming.models.audio import AudioEncoding
from svara.streaming.models.model import BaseModel


class InputAudioConfig(BaseModel):
    sampling_rate: int
    audio_encoding: AudioEncoding
    chunk_size: int
    downsampling: Optional[int] = None


class OutputAudioConfig(BaseModel):
    sampling_rate: int
    audio_encoding: AudioEncoding
