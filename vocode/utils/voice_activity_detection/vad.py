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


class BaseVoiceActivityDetectorConfig(TypedModel, type=VoiceActivityDetectorType.BASE.value):
    frame_rate: int = 16000
    min_activity_duration_seconds: float = 0.1


VoiceActivityDetectorConfigType = TypeVar("VoiceActivityDetectorConfigType", bound=BaseVoiceActivityDetectorConfig)


class BaseVoiceActivityDetector(Generic[VoiceActivityDetectorConfigType]):
    def __init__(self, config: VoiceActivityDetectorConfigType, logger: Optional[logging.Logger] = None):
        self.logger: logging.Logger = logger or logging.getLogger(__name__)
        self.config = config
        self.last_activity_timestamp = None

    def is_voice_active(self, frame: bytes) -> bool:
        raise NotImplementedError

    def get_config(self) -> BaseVoiceActivityDetectorConfig:
        return self.config

    def should_interrupt(self, frame: bytes) -> bool:
        if self.is_voice_active(frame):
            if self.last_activity_timestamp is None:
                self.last_activity_timestamp = datetime.now()
            total_seconds = (datetime.now() - self.last_activity_timestamp).total_seconds()
            if total_seconds >= self.config.min_activity_duration_seconds:
                return True
        else:
            self.last_activity_timestamp = None
