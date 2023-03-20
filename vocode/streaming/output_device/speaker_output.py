import sounddevice as sd
import numpy as np

from .base_output_device import BaseOutputDevice
from vocode.streaming.models.audio_encoding import AudioEncoding


class SpeakerOutput(BaseOutputDevice):
    DEFAULT_SAMPLING_RATE = 44100

    def __init__(
        self,
        device_info: dict,
        sampling_rate: int = None,
        audio_encoding: AudioEncoding = AudioEncoding.LINEAR16,
    ):
        self.device_info = device_info
        sampling_rate = sampling_rate or int(
            self.device_info.get("default_samplerate", self.DEFAULT_SAMPLING_RATE)
        )
        super().__init__(sampling_rate, audio_encoding)
        self.stream = sd.OutputStream(
            channels=1,
            samplerate=self.sampling_rate,
            dtype=np.int16,
            device=int(self.device_info["index"]),
        )
        self.stream.start()

    async def send_async(self, chunk):
        self.stream.write(np.frombuffer(chunk, dtype=np.int16))

    def terminate(self):
        self.stream.close()
