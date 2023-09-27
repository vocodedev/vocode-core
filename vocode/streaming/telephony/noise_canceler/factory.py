import logging
from typing import Optional

from vocode.streaming.telephony.noise_canceler.noise_canceling import NoiseCancelingConfig
from vocode.streaming.telephony.noise_canceler.noise_reduce import NoiseReduceNoiseCanceler, \
    NoiseReduceNoiseCancelingConfig
from vocode.streaming.telephony.noise_canceler.pico_voice import PicoVoiceNoiseCanceler


class NoiseCancelerFactory:
    def create_noise_canceler(
            self,
            config: NoiseCancelingConfig,
            logger: Optional[logging.Logger] = None,
    ):
        if isinstance(config, NoiseReduceNoiseCancelingConfig):
            return NoiseReduceNoiseCanceler(config, logger=logger)
        if isinstance(config, NoiseCancelingConfig):
            return PicoVoiceNoiseCanceler(config, logger=logger)
