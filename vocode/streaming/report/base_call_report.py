import logging
from enum import Enum
from typing import TypeVar, Generic, Optional

from vocode.streaming.models.model import TypedModel
from vocode.streaming.models.transcript import Transcript, Message


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

    def report(self, conversation_id: str, transcript: Transcript, slug: str):
        raise NotImplementedError

    @staticmethod
    def get_event_logs(transcript):
        logs = []
        for event_log in transcript.event_logs:
            if isinstance(event_log, Message):
                log = {
                    'text': event_log.text,
                    'sender': event_log.sender.value,
                    'timestamp': event_log.timestamp,
                    'confidence': event_log.confidence,
                }
                logs.append(log)
        return logs
