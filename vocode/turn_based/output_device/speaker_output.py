import sounddevice as sd
import numpy as np
from pydub import AudioSegment

from vocode.turn_based.output_device.base_output_device import BaseOutputDevice


class SpeakerOutput(BaseOutputDevice):
    DEFAULT_SAMPLING_RATE = 44100

    def __init__(
        self,
        device_info: dict,
        sampling_rate: int = None,
    ):
        self.device_info = device_info
        self.sampling_rate = sampling_rate or int(
            self.device_info.get("default_samplerate", self.DEFAULT_SAMPLING_RATE)
        )
        self.stream = sd.OutputStream(
            channels=1,
            samplerate=self.sampling_rate,
            dtype=np.int16,
            device=int(self.device_info["index"]),
        )
        self.stream.start()

    def send_audio(self, audio_segment: AudioSegment):
        self.stream.write(np.frombuffer(audio_segment.raw_data, dtype=np.int16))

    def terminate(self):
        self.stream.close()
