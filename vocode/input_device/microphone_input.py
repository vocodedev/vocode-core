import pyaudio
from typing import Optional
import queue

from .base_input_device import BaseInputDevice
from ..models.audio_encoding import AudioEncoding

class MicrophoneInput(BaseInputDevice):

    DEFAULT_SAMPLING_RATE = 44100
    DEFAULT_CHUNK_SIZE = 2048

    def __init__(self, pa: pyaudio.PyAudio, device_info: dict, sampling_rate: int = None, chunk_size: int = DEFAULT_CHUNK_SIZE):
        self.device_info = device_info
        sampling_rate = sampling_rate or (self.device_info.get('defaultSampleRate', self.DEFAULT_SAMPLING_RATE))
        super().__init__(int(sampling_rate), AudioEncoding.LINEAR16, chunk_size)
        self.pa = pa
        self.stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sampling_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            input_device_index=int(self.device_info['index']),
            stream_callback=self._stream_callback
        )
        self.queue = queue.Queue()

    def _stream_callback(self, in_data, *_args):
        self.queue.put_nowait(in_data)
        return (None, pyaudio.paContinue)

    def get_audio(self) -> Optional[bytes]:
        try:
            return self.queue.get_nowait()
        except queue.Empty:
            return None