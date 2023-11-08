import logging
from typing import Optional

import requests

from vocode.streaming.report.base_call_report import BaseCallReporter, CallReporterType, CallReporterConfig


class ApiCallReporterConfig(CallReporterConfig, type=CallReporterType.API.value):
    url: str


class ApiCallReporter(BaseCallReporter[ApiCallReporterConfig]):
    def __init__(self, config: ApiCallReporterConfig, logger: Optional[logging.Logger] = None):
        super().__init__(config, logger)

    def report(self, messages: list, **kwargs):
        data = {
            "messages": messages,
        }
        response = requests.post(self.config.url, data=data)
        self.logger.debug(f"Response from call reporter: {response}")
