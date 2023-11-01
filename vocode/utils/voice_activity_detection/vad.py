import logging
from enum import Enum
from typing import Generic, TypeVar, Optional

from vocode.streaming.models.model import TypedModel


class VoiceActivityDetectorType(str, Enum):
    BASE = "base_voice_activity_detector"
    OPEN_AI = "web_rtc_vad_voice_activity_detector"


class BaseVoiceActivityDetectorConfig(TypedModel, type=VoiceActivityDetectorType.BASE.value):
    frame_rate: int = 16000


VoiceActivityDetectorConfigType = TypeVar("VoiceActivityDetectorConfigType", bound=BaseVoiceActivityDetectorConfig)


class BaseVoiceActivityDetector(Generic[VoiceActivityDetectorConfigType]):
    def __init__(self, config: VoiceActivityDetectorConfigType, logger: Optional[logging.Logger] = None):
        self.logger: logging.Logger = logger or logging.getLogger(__name__)
        self.config = config

    def is_voice_active(self, frame: str) -> bool:
        raise NotImplementedError

    def get_config(self) -> BaseVoiceActivityDetectorConfig:
        return self.config
