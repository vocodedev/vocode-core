import logging
from enum import Enum
from typing import TypeVar, Generic, Optional

from vocode.streaming.models.model import TypedModel


class CallReporterType(str, Enum):
    BASE = "base_call_report"
    API = "api_call_report"


class CallReporterConfig(TypedModel, type=CallReporterType.BASE.value):
    pass


CallReporterConfigType = TypeVar("CallReporterConfigType", bound=CallReporterConfig)


class BaseCallReporter(Generic[CallReporterConfigType]):
    def __init__(self, config: CallReporterConfigType, logger: Optional[logging.Logger] = None):
        self.logger: logging.Logger = logger or logging.getLogger(__name__)
        self.config = config

    def get_config(self) -> CallReporterConfig:
        return self.config

    def report(self, messages: list) -> None:
        raise NotImplementedError
