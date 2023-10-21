import logging
from copy import deepcopy
from typing import Optional

import numpy as np

from vocode.streaming.telephony.noise_canceler.base_noise_canceler import BaseNoiseCanceler
from vocode.streaming.telephony.noise_canceler.noise_canceling import NoiseCancelingType, NoiseCancelingConfig


class PicoVoiceNoiseCancelingConfig(NoiseCancelingConfig, type=NoiseCancelingType.PICO_VOICE.value):
    access_key: str


class PicoVoiceNoiseCanceler(BaseNoiseCanceler[PicoVoiceNoiseCancelingConfig]):
    def __init__(self, noise_canceling_config: PicoVoiceNoiseCancelingConfig, logger: Optional[logging.Logger] = None):
        import pvkoala

        super().__init__(noise_canceling_config, logger)
        self.access_key = noise_canceling_config.access_key
        self.koala = pvkoala.create(access_key=self.access_key)
        self.buffer = b''

    def cancel_noise(self, audio: bytes) -> bytes:
        self.buffer += audio
        if len(self.buffer) < 256:
            return b'\xff' * 160
        input_frame = np.frombuffer(self.buffer, dtype=np.int8)
        processed = self.koala.process(input_frame[0:256])
        audio = np.array(processed, dtype=np.int8).tobytes()
        self.buffer = deepcopy(self.buffer[160:])
        return deepcopy(audio[:160])
