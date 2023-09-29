import logging
from typing import Optional

from rnnoise_wrapper import RNNoise

from vocode.streaming.telephony.noise_canceler.base_noise_canceler import BaseNoiseCanceler
from vocode.streaming.telephony.noise_canceler.noise_canceling import NoiseCancelingConfig, NoiseCancelingType


class RRNWrapperNoiseCancelingConfig(NoiseCancelingConfig, type=NoiseCancelingType.RRN_WRAPPER.value):
    sample_rate: str = 8000


class RRNWrapperNoiseCanceler(BaseNoiseCanceler[RRNWrapperNoiseCancelingConfig]):
    def __init__(self, noise_canceling_config: RRNWrapperNoiseCancelingConfig, logger: Optional[logging.Logger] = None):
        super().__init__(noise_canceling_config, logger)
        self.denoiser = RNNoise("librnnoise_default.so.0.4.1")

    def cancel_noise(self, audio: bytes) -> bytes:
        out = self.denoiser.filter(audio, sample_rate=self.noise_canceling_config.sample_rate)
        return out
