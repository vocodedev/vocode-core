from .base_output_device import BaseOutputDevice
from vocode.streaming.models.audio_encoding import AudioEncoding


class TelephoneOutput(BaseOutputDevice):
    def __init__(self):
        super().__init__(sampling_rate=8000, audio_encoding=AudioEncoding.MULAW)
