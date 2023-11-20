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

    def report(self, conversation_id: str, transcript: Transcript, vonage_uuid: Optional[str],
               twilio_sid: Optional[str], from_phone: Optional[str], to_phone: Optional[str]):
        logs = self.get_event_logs(transcript)
        data = {
            "conversation_id": conversation_id,
            "logs": logs,
            "twilio_sid": twilio_sid,
            "vonage_uuid": vonage_uuid,
            "start_time": transcript.start_time,
            "from_phone": from_phone,
            "to_phone": to_phone,
        }
        self.logger.debug(f"Data to call reporter: {data}")
        response = requests.post(self.config.url, json=data)
        self.logger.debug(f"Response from call reporter: {response}")
