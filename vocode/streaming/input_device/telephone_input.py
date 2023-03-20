from vocode.streaming.input_device.base_input_device import (
    BaseInputDevice,
)
from vocode.streaming.models.audio_encoding import AudioEncoding


class TelephoneInput(BaseInputDevice):
    def __init__(self):
        super().__init__(
            sampling_rate=8000, audio_encoding=AudioEncoding.MULAW, chunk_size=160
        )
