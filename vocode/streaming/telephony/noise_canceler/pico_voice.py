import logging
from typing import Optional

import numpy as np
import pvkoala

from vocode.streaming.telephony.noise_canceler.base_noise_canceler import BaseNoiseCanceler
from vocode.streaming.telephony.noise_canceler.noise_canceling import NoiseCancelingType, NoiseCancelingConfig


class PicoVoiceNoiceCancelingConfig(NoiseCancelingConfig, type=NoiseCancelingType.PICO_VOICE.value):
    access_key: str


class PicoVoiceNoiseCanceler(BaseNoiseCanceler[PicoVoiceNoiceCancelingConfig]):
    def __init__(self, noise_canceling_config: PicoVoiceNoiceCancelingConfig, logger: Optional[logging.Logger] = None):
        super().__init__(noise_canceling_config, logger)
        self.access_key = noise_canceling_config.access_key
        self.koala = pvkoala.create(access_key=self.access_key)

    def cancel_noise(self, audio: bytes) -> bytes:
        audio += b'\xff' * (256 - len(audio))
        input_frame = np.frombuffer(audio, dtype=np.int8)
        processed = self.koala.process(input_frame[0:256])
        audio = np.array(processed, dtype=np.int8).tobytes()
        return audio[:160]
