import logging
from typing import Optional

import numpy as np

from vocode.utils.voice_activity_detection.vad import BaseVoiceActivityDetector, BaseVoiceActivityDetectorConfig, \
    VoiceActivityDetectorType


class WebRTCVoiceActivityDetectorConfig(BaseVoiceActivityDetectorConfig, type=VoiceActivityDetectorType.WEB_RTC.value):
    pass


class WebRTCVoiceActivityDetector(BaseVoiceActivityDetector[WebRTCVoiceActivityDetectorConfig]):
    def __init__(self, config: WebRTCVoiceActivityDetectorConfig, logger: Optional[logging.Logger] = None):
        import webrtcvad
        super().__init__(config, logger)
        self.vad = webrtcvad.Vad()

    def is_voice_active(self, frame: bytes) -> bool:
        bytes_frame = np.frombuffer(frame, dtype=np.int8)
        return self.vad.is_speech(bytes_frame, self.config.frame_rate)
