import wave
import queue
import numpy as np

from .base_output_device import BaseOutputDevice
from vocode.streaming.models.audio_encoding import AudioEncoding


class FileOutputDevice(BaseOutputDevice):
    DEFAULT_SAMPLING_RATE = 44100

    def __init__(
        self,
        file_path: str,
        sampling_rate: int = DEFAULT_SAMPLING_RATE,
        audio_encoding: AudioEncoding = AudioEncoding.LINEAR16,
    ):
        super().__init__(sampling_rate, audio_encoding)
        self.blocksize = self.sampling_rate
        self.file_path = file_path
        self.queue: queue.Queue[np.ndarray] = queue.Queue()

    def consume_nonblocking(self, chunk):
        chunk_arr = np.frombuffer(chunk, dtype=np.int16)
        for i in range(0, chunk_arr.shape[0], self.blocksize):
            block = np.zeros(self.blocksize, dtype=np.int16)
            size = min(self.blocksize, chunk_arr.shape[0] - i)
            block[:size] = chunk_arr[i : i + size]
            self.queue.put_nowait(block)

    def terminate(self):
        with wave.open(self.file_path, "wb") as wav:
            wav.setnchannels(1)  # Mono channel
            wav.setsampwidth(2)  # 16-bit samples
            wav.setframerate(self.sampling_rate)
            while True:
                try:
                    block = self.queue.get()
                    wav.writeframes(block)
                except queue.Empty:
                    break
