import logging
from enum import Enum
from typing import Generic, TypeVar, Optional

from vocode.streaming.models.model import TypedModel


class ContextTrackerType(str, Enum):
    BASE = "base_context_tracker"
    OPEN_AI = "open_ai_context_tracker"


class BaseContextTrackerConfig(TypedModel, type=ContextTrackerType.BASE.value):
    pass


ContextTrackerConfigType = TypeVar("ContextTrackerConfigType", bound=BaseContextTrackerConfig)


class BaseContextTracker(Generic[ContextTrackerConfigType]):
    def __init__(self, config: ContextTrackerConfigType, logger: Optional[logging.Logger] = None):
        self.logger = logger
        self.config = config

    def is_part_of_context(self, user_message: str) -> bool:
        raise NotImplementedError

    def get_context_tracker_config(self) -> BaseContextTrackerConfig:
        return self.config
