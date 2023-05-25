from vocode.streaming.models.audio_encoding import AudioEncoding
import janus
from vocode.streaming.input_device.base_input_device import BaseInputDevice
import wave
import struct
import numpy as np


class FileInputDevice(BaseInputDevice):
    DEFAULT_SAMPLING_RATE = 44100
    DEFAULT_CHUNK_SIZE = 2048

    def __init__(
        self,
        file_path: str,
        sampling_rate: int = DEFAULT_SAMPLING_RATE,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        silent_duration: float = 3.0,
    ):
        super().__init__(sampling_rate, AudioEncoding.LINEAR16, chunk_size)

        self.queue: janus.Queue[bytes] = janus.Queue()

        with wave.open(file_path, "rb") as wave_file:
            n_channels = wave_file.getnchannels()
            frame_rate = wave_file.getframerate()
            n_frames = wave_file.getnframes()
            self.total_chunks = n_frames // chunk_size
            if n_channels != 1:
                raise ValueError("Only mono audio is supported")
            if frame_rate != sampling_rate:
                raise ValueError(
                    f"Sampling rate of file ({frame_rate}) does not match "
                    + f"sampling rate of input device ({sampling_rate}). Only "
                    + f"{self.DEFAULT_SAMPLING_RATE} is supported."
                )

            for _ in range(self.total_chunks):
                chunk_data = wave_file.readframes(chunk_size)
                self.queue.sync_q.put_nowait(chunk_data)

            silent_chunk_data = self.generate_silent_chunk(silent_duration)
            self.queue.sync_q.put_nowait(silent_chunk_data)

    def generate_silent_chunk(self, duration: float) -> bytes:
        num_samples = int(self.sampling_rate * duration)
        samples = np.zeros(num_samples, dtype=np.int16)
        silent_wave = struct.pack("<" + "h" * len(samples), *samples)
        return silent_wave

    async def get_audio(self) -> bytes:
        return await self.queue.async_q.get()
