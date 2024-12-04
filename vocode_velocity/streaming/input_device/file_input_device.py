import struct
import wave

import janus
import numpy as np

from vocode.streaming.input_device.base_input_device import BaseInputDevice
from vocode.streaming.models.audio import AudioEncoding


class FileInputDevice(BaseInputDevice):
    DEFAULT_SAMPLING_RATE = 44100
    DEFAULT_CHUNK_SIZE = 2048
    DEFAULT_SILENT_DURATION = 3.0

    def __init__(
        self,
        file_path: str,
        sampling_rate: int = DEFAULT_SAMPLING_RATE,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        silent_duration: float = DEFAULT_SILENT_DURATION,
        skip_initial_load=False,
    ):
        super().__init__(sampling_rate, AudioEncoding.LINEAR16, chunk_size)

        self.queue: janus.Queue[bytes] = janus.Queue()
        self.file_path = file_path
        self.silent_duration = silent_duration
        if not skip_initial_load:
            self.load()

    def generate_silent_chunk(self, duration: float) -> bytes:
        num_samples = int(self.sampling_rate * duration)
        samples = np.zeros(num_samples, dtype=np.int16)
        silent_wave = struct.pack("<" + "h" * len(samples), *samples)
        return silent_wave

    async def get_audio(self) -> bytes:
        return await self.queue.async_q.get()

    def is_done(self) -> bool:
        return self.queue.sync_q.qsize() == 0

    def load(self):
        with wave.open(self.file_path, "rb") as wave_file:
            n_channels = wave_file.getnchannels()
            frame_rate = wave_file.getframerate()
            n_frames = wave_file.getnframes()
            self.duration = n_frames / frame_rate
            self.total_chunks = n_frames // self.chunk_size
            if n_channels != 1:
                raise ValueError("Only mono audio is supported")
            if frame_rate != self.sampling_rate:
                raise ValueError(
                    f"Sampling rate of file ({frame_rate}) does not match "
                    + f"sampling rate of input device ({self.sampling_rate}). Only "
                    + f"{self.DEFAULT_SAMPLING_RATE} is supported."
                )

            for _ in range(self.total_chunks):
                chunk_data = wave_file.readframes(self.chunk_size)
                self.queue.sync_q.put_nowait(chunk_data)

            silent_chunk_data = self.generate_silent_chunk(self.silent_duration)
            self.queue.sync_q.put_nowait(silent_chunk_data)
