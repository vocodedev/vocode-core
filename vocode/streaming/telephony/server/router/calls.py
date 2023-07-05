from typing import Optional
import logging

from fastapi import APIRouter, HTTPException, WebSocket
from vocode.streaming.agent.factory import AgentFactory
from vocode.streaming.models.telephony import (
    BaseCallConfig,
    TwilioCallConfig,
    VonageCallConfig,
)
from vocode.streaming.synthesizer.factory import SynthesizerFactory
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)

from vocode.streaming.telephony.conversation.call import Call
from vocode.streaming.telephony.conversation.twilio_call import TwilioCall
from vocode.streaming.telephony.conversation.vonage_call import VonageCall
from vocode.streaming.transcriber.factory import TranscriberFactory
from vocode.streaming.utils.base_router import BaseRouter
from vocode.streaming.utils.events_manager import EventsManager
from opentelemetry import trace
import requests
import os
import json

from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

class DatabaseExporter:
    def __init__(self, conversation_id):
        self.conversation_id = conversation_id
        self.base_url = f"https://api.airtable.com/v0/{os.getenv('AIRTABLE_BASE_ID')}/logs"
        self.headers = {
            "Authorization": f"Bearer {os.getenv('AIRTABLE_ACCESS_TOKEN')}",
            "Content-Type": "application/json"
        }

    def export(self, spans):
        record_id = self.get_record_id()
        record_data = {"conversation_id": self.conversation_id, "log": []}

        for span in spans:
            record_data["log"].append({
                "name": span.name,
                "duration": (span.end_time - span.start_time) / 1e9,
            })

        record_data["log"] = json.dumps(record_data["log"])

        payload = {"records": [{"id": record_id, "fields": record_data}]}

        response = requests.patch(self.base_url, headers=self.headers, json=payload)

        if response.status_code == 200:
            print("Successfully logged to the database")
        else:
            print("Failed to log to the database", response.status_code, response.text)

    def get_record_id(self):
        params = {
            "filterByFormula": f"{{conversation_id}} = '{self.conversation_id}'",
            "maxRecords": 1
        }

        response = requests.get(self.base_url, headers=self.headers, params=params)

        if response.status_code == 200:
            data = response.json()
            records = data.get('records', [])
            if records:
                return records[0].get('id')
        return None

    def shutdown(self):
        pass

class CallsRouter(BaseRouter):
    def __init__(
        self,
        base_url: str,
        config_manager: BaseConfigManager,
        transcriber_factory: TranscriberFactory = TranscriberFactory(),
        agent_factory: AgentFactory = AgentFactory(),
        synthesizer_factory: SynthesizerFactory = SynthesizerFactory(),
        events_manager: Optional[EventsManager] = None,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__()
        self.base_url = base_url
        self.config_manager = config_manager
        self.transcriber_factory = transcriber_factory
        self.agent_factory = agent_factory
        self.synthesizer_factory = synthesizer_factory
        self.events_manager = events_manager
        self.logger = logger or logging.getLogger(__name__)
        self.router = APIRouter()
        self.router.websocket("/connect_call/{id}")(self.connect_call)

    def _from_call_config(
        self,
        base_url: str,
        call_config: BaseCallConfig,
        config_manager: BaseConfigManager,
        conversation_id: str,
        logger: logging.Logger,
        transcriber_factory: TranscriberFactory = TranscriberFactory(),
        agent_factory: AgentFactory = AgentFactory(),
        synthesizer_factory: SynthesizerFactory = SynthesizerFactory(),
        events_manager: Optional[EventsManager] = None,
    ):
        if isinstance(call_config, TwilioCallConfig):
            return TwilioCall(
                to_phone=call_config.to_phone,
                from_phone=call_config.from_phone,
                base_url=base_url,
                logger=logger,
                config_manager=config_manager,
                agent_config=call_config.agent_config,
                transcriber_config=call_config.transcriber_config,
                synthesizer_config=call_config.synthesizer_config,
                twilio_config=call_config.twilio_config,
                twilio_sid=call_config.twilio_sid,
                conversation_id=conversation_id,
                transcriber_factory=transcriber_factory,
                agent_factory=agent_factory,
                synthesizer_factory=synthesizer_factory,
                events_manager=events_manager,
            )
        elif isinstance(call_config, VonageCallConfig):
            return VonageCall(
                to_phone=call_config.to_phone,
                from_phone=call_config.from_phone,
                base_url=base_url,
                logger=logger,
                config_manager=config_manager,
                agent_config=call_config.agent_config,
                transcriber_config=call_config.transcriber_config,
                synthesizer_config=call_config.synthesizer_config,
                vonage_config=call_config.vonage_config,
                vonage_uuid=call_config.vonage_uuid,
                conversation_id=conversation_id,
                transcriber_factory=transcriber_factory,
                agent_factory=agent_factory,
                synthesizer_factory=synthesizer_factory,
                events_manager=events_manager,
                output_to_speaker=call_config.output_to_speaker,
            )
        else:
            raise ValueError(f"Unknown call config type {call_config.type}")

    async def connect_call(self, websocket: WebSocket, id: str):
        span_exporter = InMemorySpanExporter()
        database_exporter = DatabaseExporter(id)
        span_processor = BatchSpanProcessor(span_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("connect_call") as conversation:
            conversation.set_attribute("conversation_id", id)
            await websocket.accept()
            self.logger.debug("Phone WS connection opened for chat {}".format(id))
            call_config = await self.config_manager.get_config(id)
            if not call_config:
                raise HTTPException(status_code=400, detail="No active phone call")

            call = self._from_call_config(
                base_url=self.base_url,
                call_config=call_config,
                config_manager=self.config_manager,
                conversation_id=id,
                transcriber_factory=self.transcriber_factory,
                agent_factory=self.agent_factory,
                synthesizer_factory=self.synthesizer_factory,
                events_manager=self.events_manager,
                logger=self.logger,
            )

            await call.attach_ws_and_start(websocket)
            self.logger.debug("Phone WS connection closed for chat {}".format(id))
        child_spans = span_exporter.get_finished_spans()
        database_exporter.export(child_spans)
        

    def get_router(self) -> APIRouter:
        return self.router
