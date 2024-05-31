import io
import wave
from typing import Optional

import numpy as np
import sounddevice as sd
from pydub import AudioSegment

from vocode.turn_based.input_device.base_input_device import BaseInputDevice


class MicrophoneInput(BaseInputDevice):
    DEFAULT_SAMPLING_RATE = 44100
    DEFAULT_CHUNK_SIZE = 2048

    def __init__(
        self,
        device_info: dict,
        sampling_rate: Optional[int] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        self.device_info = device_info
        self.sampling_rate = sampling_rate or (
            self.device_info.get("default_samplerate", self.DEFAULT_SAMPLING_RATE)
        )
        self.chunk_size = chunk_size
        self.buffer: Optional[io.BytesIO] = None
        self.wave_writer: Optional[wave.Wave_write] = None
        self.stream = sd.InputStream(
            dtype=np.int16,
            channels=1,
            samplerate=self.sampling_rate,
            blocksize=self.chunk_size,
            device=int(self.device_info["index"]),
            callback=self._stream_callback,
        )
        self.active = False

    @classmethod
    def from_default_device(cls, sampling_rate: Optional[int] = None):
        return cls(sd.query_devices(kind="input"), sampling_rate)

    def _stream_callback(self, in_data: np.ndarray, *_args):
        if self.active and self.wave_writer is not None:
            audio_bytes = in_data.tobytes()
            self.wave_writer.writeframes(audio_bytes)

    def create_buffer(self):
        in_memory_wav = io.BytesIO()
        wave_writer = wave.open(in_memory_wav, "wb")
        wave_writer.setnchannels(1)
        wave_writer.setsampwidth(2)
        wave_writer.setframerate(self.sampling_rate)
        return in_memory_wav, wave_writer

    def start_listening(self):
        self.buffer, self.wave_writer = self.create_buffer()
        self.active = True
        self.stream.start()

    def end_listening(self) -> AudioSegment:
        self.stream.stop()
        self.active = False
        if self.buffer is not None:
            self.buffer.seek(0)
        return AudioSegment.from_wav(self.buffer)  # type: ignore
