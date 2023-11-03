import logging
from typing import Optional

import numpy as np

from vocode.utils.voice_activity_detection.vad import BaseVoiceActivityDetector, BaseVoiceActivityDetectorConfig, \
    VoiceActivityDetectorType


class WebRTCVoiceActivityDetectorConfig(BaseVoiceActivityDetectorConfig, type=VoiceActivityDetectorType.WEB_RTC.value):
    mode: int = 3


class WebRTCVoiceActivityDetector(BaseVoiceActivityDetector[WebRTCVoiceActivityDetectorConfig]):
    def __init__(self, config: WebRTCVoiceActivityDetectorConfig, logger: Optional[logging.Logger] = None):
        import webrtcvad
        super().__init__(config, logger)
        self.vad = webrtcvad.Vad(self.config.mode)

    def is_voice_active(self, frame: bytes) -> bool:
        return self.vad.is_speech(frame, self.config.frame_rate)
