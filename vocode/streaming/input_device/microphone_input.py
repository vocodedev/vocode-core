import sounddevice as sd
import numpy as np
from typing import Optional
import queue
import wave

from vocode.streaming.input_device.base_input_device import BaseInputDevice
from vocode.streaming.models.audio_encoding import AudioEncoding


class MicrophoneInput(BaseInputDevice):
    DEFAULT_SAMPLING_RATE = 44100
    DEFAULT_CHUNK_SIZE = 2048

    def __init__(
        self,
        device_info: dict,
        sampling_rate: int = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        microphone_gain: int = 1,
    ):
        self.device_info = device_info
        sampling_rate = sampling_rate or (
            self.device_info.get("default_samplerate", self.DEFAULT_SAMPLING_RATE)
        )
        super().__init__(int(sampling_rate), AudioEncoding.LINEAR16, chunk_size)
        self.stream = sd.InputStream(
            dtype=np.int16,
            channels=1,
            samplerate=self.sampling_rate,
            blocksize=self.chunk_size,
            device=int(self.device_info["index"]),
            callback=self._stream_callback,
        )
        self.stream.start()
        self.queue = queue.Queue()
        self.microphone_gain = microphone_gain

    def _stream_callback(self, in_data: np.ndarray, *_args):
        if self.microphone_gain > 1:
            in_data = in_data * (2 ^ self.microphone_gain)
        else:
            in_data = in_data // (2 ^ self.microphone_gain)
        audio_bytes = in_data.tobytes()
        self.queue.put_nowait(audio_bytes)

    def get_audio(self) -> Optional[bytes]:
        try:
            return self.queue.get_nowait()
        except queue.Empty:
            return None
