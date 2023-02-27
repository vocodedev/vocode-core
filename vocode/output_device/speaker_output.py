import pyaudio

from .base_output_device import BaseOutputDevice
from ..models.audio_encoding import AudioEncoding

class SpeakerOutput(BaseOutputDevice):

    DEFAULT_SAMPLING_RATE = 44100

    def __init__(self, pa: pyaudio.PyAudio, device_info: dict, sampling_rate: int = None, audio_encoding: AudioEncoding = AudioEncoding.LINEAR16):
        self.device_info = device_info
        sampling_rate = sampling_rate or int(self.device_info.get('defaultSampleRate', self.DEFAULT_SAMPLING_RATE))
        super().__init__(sampling_rate, audio_encoding)
        self.pa = pa
        self.stream = self.pa.open(
            output=True,
            channels=1,
            rate=self.sampling_rate,
            format=pyaudio.paInt16,
            output_device_index=int(self.device_info['index'])
        )

    async def send_async(self, chunk):
        self.stream.write(chunk)

    def terminate(self):
        self.stream.close()
        self.pa.close()