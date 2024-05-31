import queue
from typing import Optional

from vocode.streaming.models.audio import AudioEncoding


class BaseInputDevice:
    def __init__(self, sampling_rate: int, audio_encoding: AudioEncoding, chunk_size: int):
        self.sampling_rate = sampling_rate
        self.audio_encoding = audio_encoding
        self.chunk_size = chunk_size

    async def get_audio(self) -> bytes:
        raise NotImplementedError
