from __future__ import annotations

import queue
import typing
import wave
from typing import Optional

import janus
import numpy as np
import sounddevice as sd

from vocode.streaming.input_device.base_input_device import BaseInputDevice
from vocode.streaming.models.audio import AudioEncoding


class MicrophoneInput(BaseInputDevice):
    DEFAULT_SAMPLING_RATE = 44100
    DEFAULT_CHUNK_SIZE = 2048

    def __init__(
        self,
        device_info: dict,
        sampling_rate: Optional[int] = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        microphone_gain: int = 1,
    ):
        self.device_info = device_info
        super().__init__(
            sampling_rate
            or (
                typing.cast(
                    int,
                    self.device_info.get("default_samplerate", self.DEFAULT_SAMPLING_RATE),
                )
            ),
            AudioEncoding.LINEAR16,
            chunk_size,
        )
        self.stream = sd.InputStream(
            dtype=np.int16,
            channels=1,
            samplerate=self.sampling_rate,
            blocksize=self.chunk_size,
            device=int(self.device_info["index"]),
            callback=self._stream_callback,
        )
        self.stream.start()
        self.queue: janus.Queue[bytes] = janus.Queue()
        self.microphone_gain = microphone_gain

    def _stream_callback(self, in_data: np.ndarray, *_args):
        if self.microphone_gain > 1:
            in_data = in_data * (2 ^ self.microphone_gain)
        else:
            in_data = in_data // (2 ^ self.microphone_gain)
        audio_bytes = in_data.tobytes()
        self.queue.sync_q.put_nowait(audio_bytes)

    async def get_audio(self) -> bytes:
        return await self.queue.async_q.get()

    @classmethod
    def from_default_device(cls, sampling_rate: Optional[int] = None):
        return cls(sd.query_devices(kind="input"), sampling_rate)
