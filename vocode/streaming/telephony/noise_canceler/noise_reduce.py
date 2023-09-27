import logging
from typing import Optional

import noisereduce as nr
import numpy as np

from vocode.streaming.telephony.noise_canceler.base_noise_canceler import BaseNoiseCanceler
from vocode.streaming.telephony.noise_canceler.noise_canceling import NoiseCancelingConfig, NoiseCancelingType


class NoiseReduceNoiseCancelingConfig(NoiseCancelingConfig, type=NoiseCancelingType.NOISE_REDUCE.value):
    use_torch: bool = False


class NoiseReduceNoiseCanceler(BaseNoiseCanceler[NoiseReduceNoiseCancelingConfig]):
    def __init__(self, noise_canceling_config: NoiseReduceNoiseCancelingConfig,
                 logger: Optional[logging.Logger] = None):
        super().__init__(noise_canceling_config, logger)

    def cancel_noise(self, audio: bytes) -> bytes:
        data = np.frombuffer(audio, dtype=np.int8)
        reduced_noise = nr.reduce_noise(y=data, sr=8000, use_torch=self.noise_canceling_config.use_torch)
        return np.array(reduced_noise, dtype=np.int8).tobytes()
