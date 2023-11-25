import logging
from typing import Optional

from vocode.streaming.voice_activity_detection.silero_vad import SileroVoiceActivityDetectorConfig, \
    SileroVoiceActivityDetector
from vocode.streaming.voice_activity_detection.vad import BaseVoiceActivityDetectorConfig
from vocode.streaming.voice_activity_detection.webrtc_vad import WebRTCVoiceActivityDetectorConfig, \
    WebRTCVoiceActivityDetector


class VoiceActivityDetectorFactory:
    @staticmethod
    def create_voice_activity_detector(
            vad_config: Optional[BaseVoiceActivityDetectorConfig],
            logger: Optional[logging.Logger] = None,
    ):
        if isinstance(vad_config, WebRTCVoiceActivityDetectorConfig):
            return WebRTCVoiceActivityDetector(vad_config, logger=logger)
        if isinstance(vad_config, SileroVoiceActivityDetectorConfig):
            return SileroVoiceActivityDetector(vad_config, logger=logger)