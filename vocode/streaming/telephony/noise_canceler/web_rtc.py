import logging
from copy import deepcopy
from typing import Optional

from vocode.streaming.telephony.noise_canceler.base_noise_canceler import BaseNoiseCanceler
from vocode.streaming.telephony.noise_canceler.noise_canceling import NoiseCancelingConfig, NoiseCancelingType


class WebRTCNoiseCancelingConfig(NoiseCancelingConfig, type=NoiseCancelingType.WEB_RTC.value):
    auto_gain_dbfs: int = 3  # [0, 31]
    noise_suppression_level: int = 2


class WebRTCNoiseCanceler(BaseNoiseCanceler[WebRTCNoiseCancelingConfig]):

    def __init__(self, noise_canceling_config: WebRTCNoiseCancelingConfig, logger: Optional[logging.Logger] = None):
        from webrtc_noise_gain_cpp import AudioProcessor

        super().__init__(noise_canceling_config, logger)
        self.audio_processor = AudioProcessor(self.noise_canceling_config.auto_gain_dbfs,
                                              self.noise_canceling_config.noise_suppression_level)
        self.buffer = b''

    def cancel_noise(self, audio: bytes) -> bytes:
        self.buffer += audio
        if len(self.buffer) < 320:
            return b'\xff' * 160

        out = self.audio_processor.Process10ms(self.buffer)
        self.buffer = deepcopy(self.buffer[160:])
        return out.audio[:160]
