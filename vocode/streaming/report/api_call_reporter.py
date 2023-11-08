import logging
from typing import Optional

import requests

from vocode.streaming.models.transcript import Transcript
from vocode.streaming.report.base_call_report import BaseCallReporter, CallReporterType, CallReporterConfig


class ApiCallReporterConfig(CallReporterConfig, type=CallReporterType.API.value):
    url: str


class ApiCallReporter(BaseCallReporter[ApiCallReporterConfig]):
    def __init__(self, config: ApiCallReporterConfig, logger: Optional[logging.Logger] = None):
        super().__init__(config, logger)

    def report(self, conversation_id: str, transcript: Transcript):
        logs = self.get_event_logs(transcript)
        data = {
            "conversation_id": conversation_id,
            "logs": logs,
            "start_time": transcript.start_time,
        }
        response = requests.post(self.config.url, data=data)
        self.logger.debug(f"Response from call reporter: {response}")
