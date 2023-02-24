from ..models.audio_encoding import AudioEncoding
import queue
from typing import Optional

class BaseInputDevice():

    def __init__(self, sampling_rate: int, audio_encoding: AudioEncoding, chunk_size: int):
        self.sampling_rate = sampling_rate
        self.audio_encoding = audio_encoding
        self.chunk_size = chunk_size
        self.queue = queue.Queue()

    def get_audio(self) -> Optional[bytes]:
        raise NotImplementedError