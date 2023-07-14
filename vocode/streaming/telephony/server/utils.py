import logging
from opentelemetry import trace
import os
import aiohttp
import json


class SpanLogHandler(logging.Handler):
    def emit(self, record):
        self.format(record)
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            name="log_span",
        ) as span:
            span.set_attribute("message", record.message)
            span.set_attribute("level", record.levelname)

class DatabaseExporter:
    def __init__(self, conversation_id, logger):
        self.conversation_id = conversation_id
        self.base_url = (
            f"https://api.airtable.com/v0/{os.getenv('AIRTABLE_BASE_ID')}/logs"
        )
        self.headers = {
            "Authorization": f"Bearer {os.getenv('AIRTABLE_ACCESS_TOKEN')}",
            "Content-Type": "application/json",
        }
        self.logger = logger

    async def export(self, spans, from_phone, to_phone):
        async with aiohttp.ClientSession() as session:
            record_data = {"conversation_id": self.conversation_id, "log": [], "from_phone": from_phone, "to_phone": to_phone}
            for span in spans:
                if span.name == "log_span":
                    if span.attributes["level"] == "ERROR":
                        # Can send logs to Slack from here
                        record_data["log"].append({"ERROR": span.attributes["message"]})
                        record_data.setdefault("error_log", []).append({"ERROR": span.attributes["message"]})
                    else:
                        record_data["log"].append({"message": span.attributes["message"]})
                else:
                    record_data["log"].append({
                        "name": span.name,
                        "duration": (span.end_time - span.start_time) / 1e9,
                    })
            record_data["log"] = json.dumps(record_data["log"], indent=4)
            if "error_log" in record_data: record_data["error_log"] = json.dumps(record_data["error_log"], indent=4)
            payload = {"performUpsert": {"fieldsToMergeOn": ["conversation_id"]}, "records": [{"fields": record_data}]}
            async with session.patch(self.base_url, headers=self.headers, json=payload) as response:
                if response.status == 200:
                    self.logger.debug("Successfully logged to the database")
                else:
                    resp = await response.text()
                    self.logger.debug(f"Failed to log to the database, {response.status}, {resp}")
