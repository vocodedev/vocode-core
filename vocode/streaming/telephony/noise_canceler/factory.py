import logging
from typing import Optional

from vocode.streaming.telephony.noise_canceler.noise_canceling import NoiseCancelingConfig
from vocode.streaming.telephony.noise_canceler.noise_reduce import NoiseReduceNoiseCanceler, \
    NoiseReduceNoiseCancelingConfig
from vocode.streaming.telephony.noise_canceler.pico_voice import PicoVoiceNoiseCanceler, PicoVoiceNoiseCancelingConfig
from vocode.streaming.telephony.noise_canceler.rnn_noise_wrapper import RRNWrapperNoiseCancelingConfig, \
    RRNWrapperNoiseCanceler
from vocode.streaming.telephony.noise_canceler.web_rtc import WebRTCNoiseCanceler, WebRTCNoiseCancelingConfig


class NoiseCancelerFactory:
    def create_noise_canceler(
            self,
            config: NoiseCancelingConfig,
            logger: Optional[logging.Logger] = None,
    ):
        if isinstance(config, WebRTCNoiseCancelingConfig):
            logger.debug("using WebRTC noise canceler")
            return WebRTCNoiseCanceler(config, logger=logger)
        # if isinstance(config, RRNWrapperNoiseCancelingConfig):
        #     return RRNWrapperNoiseCanceler(config, logger=logger)
        if isinstance(config, NoiseReduceNoiseCancelingConfig):
            return NoiseReduceNoiseCanceler(config, logger=logger)
        if isinstance(config, PicoVoiceNoiseCancelingConfig):
            return PicoVoiceNoiseCanceler(config, logger=logger)
