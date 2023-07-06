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


class DatabaseExporter:
    def __init__(self, conversation_id):
        self.conversation_id = conversation_id
        self.base_url = (
            f"https://api.airtable.com/v0/{os.getenv('AIRTABLE_BASE_ID')}/logs"
        )
        self.headers = {
            "Authorization": f"Bearer {os.getenv('AIRTABLE_ACCESS_TOKEN')}",
            "Content-Type": "application/json",
        }

    async def export(self, spans):
        async with aiohttp.ClientSession() as session:
            record_id = await self.get_record_id(session)
            record_data = {"conversation_id": self.conversation_id, "log": []}
            for span in spans:
                if span.name == "log_span":
                    record_data["log"].append({"message": span.attributes["message"]})
                else:
                    record_data["log"].append(
                        {
                            "name": span.name,
                            "duration": (span.end_time - span.start_time) / 1e9,
                        }
                    )
            record_data["log"] = json.dumps(record_data["log"], indent=4)
            payload = {"records": [{"id": record_id, "fields": record_data}]}
            async with session.patch(
                self.base_url, headers=self.headers, json=payload
            ) as response:
                if response.status == 200:
                    print("Successfully logged to the database")
                else:
                    print(
                        "Failed to log to the database",
                        response.status,
                        await response.text(),
                    )

    async def get_record_id(self, session):
        params = {
            "filterByFormula": f"{{conversation_id}} = '{self.conversation_id}'",
            "maxRecords": 1,
        }
        async with session.get(
            self.base_url, headers=self.headers, params=params
        ) as response:
            if response.status == 200:
                data = await response.json()
                records = data.get("records", [])
                if records:
                    return records[0].get("id")
        return None
