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

    def report(self, conversation_id: str, transcript: Transcript, slug: str):
        logs = self.get_event_logs(transcript)
        data = {
            "conversation_id": conversation_id,
            "logs": logs,
            "slug": slug,
            "start_time": transcript.start_time,
        }
        self.logger.debug(f"Data to call reporter: {data}")
        response = requests.post(self.config.url, json=data)
        self.logger.debug(f"Response from call reporter: {response}")
