import logging
from typing import Optional

from vocode.streaming.report.api_call_reporter import ApiCallReporterConfig, ApiCallReporter
from vocode.streaming.report.base_call_report import CallReporterConfig


class CallReporterFactory:
    @staticmethod
    def create_call_reporter(config: CallReporterConfig, logger: Optional[logging.Logger] = None):
        if isinstance(config, ApiCallReporterConfig):
            return ApiCallReporter(config, logger)
