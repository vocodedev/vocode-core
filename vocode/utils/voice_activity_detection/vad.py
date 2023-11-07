import logging
import time
from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar, Optional

from vocode.streaming.models.model import TypedModel


class VoiceActivityDetectorType(str, Enum):
    BASE = "base_voice_activity_detector"
    WEB_RTC = "web_rtc_voice_activity_detector"
    SILERO = "silero_voice_activity_detector"
    LIB_ROSA = "librosa_voice_activity_detector"


class BaseVoiceActivityDetectorConfig(TypedModel, type=VoiceActivityDetectorType.BASE.value):
    frame_rate: int = 16000
    min_activity_duration_seconds: float = 0.4
    silence_break_threshold: float = 0.1
    speach_ratio: float = .8


VoiceActivityDetectorConfigType = TypeVar("VoiceActivityDetectorConfigType", bound=BaseVoiceActivityDetectorConfig)


class BaseVoiceActivityDetector(Generic[VoiceActivityDetectorConfigType]):
    def __init__(self, config: VoiceActivityDetectorConfigType, logger: Optional[logging.Logger] = None):
        self.logger: logging.Logger = logger or logging.getLogger(__name__)
        self.config = config
        self.speach_start_timestamp = None
        self.activity_state = {True: 0, False: 0}
        self.is_speaking = False
        self.is_interrupted = False

    def is_voice_active(self, frame: bytes) -> bool:
        raise NotImplementedError

    def get_config(self) -> BaseVoiceActivityDetectorConfig:
        return self.config

    def should_interrupt(self, frame: bytes) -> bool:
        now = datetime.now()
        is_voice_active = self.is_voice_active(frame)

        self.activity_state[is_voice_active] += 1

        if is_voice_active and self.speach_start_timestamp is None:
            self.activity_state = {True: 0, False: 0}
            self.speach_start_timestamp = now

        if (now - self.speach_start_timestamp).total_seconds() > self.config.min_activity_duration_seconds:
            speach_ratio = self.activity_state[True] / (self.activity_state[True] + self.activity_state[False])
            if speach_ratio > self.config.speach_ratio:
                if self.is_interrupted:
                    return False
                self.is_interrupted = True
                return True
            else:
                self.is_interrupted = False
                self.speach_start_timestamp = None
                return False
