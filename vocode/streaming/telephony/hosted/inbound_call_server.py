from fastapi import FastAPI, Form, Response
from typing import Optional
import requests
import uvicorn

import vocode
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.telephony import (
    CallEntity,
    CreateInboundCall,
    TwilioConfig,
    TwilioConfig,
    VonageConfig,
)
from vocode.streaming.telephony.server.base import VonageAnswerRequest


class InboundCallServer:
    def __init__(
        self,
        agent_config: AgentConfig,
        transcriber_config: Optional[TranscriberConfig] = None,
        synthesizer_config: Optional[SynthesizerConfig] = None,
        response_on_rate_limit: Optional[str] = None,
        vonage_config: Optional[VonageConfig] = None,
        twilio_config: Optional[TwilioConfig] = None,
    ):
        self.agent_config = agent_config
        self.transcriber_config = transcriber_config
        self.synthesizer_config = synthesizer_config
        self.app = FastAPI()

        self.vonage_config = vonage_config
        self.twilio_config = twilio_config
        self.create_inbound_route()
        self.response_on_rate_limit = (
            response_on_rate_limit
            or "The line is really busy right now, check back later!"
        )
        self.vocode_inbound_call_url = f"https://{vocode.base_url}/create_inbound_call"

    def create_inbound_route(self):
        async def handle_vonage_call(vonage_answer_request: VonageAnswerRequest):
            response = requests.post(
                self.vocode_inbound_call_url,
                headers={"Authorization": f"Bearer {vocode.api_key}"},
                json=CreateInboundCall(
                    recipient=CallEntity(
                        phone_number=vonage_answer_request.to,
                    ),
                    caller=CallEntity(
                        phone_number=vonage_answer_request.from_,
                    ),
                    agent_config=self.agent_config,
                    vonage_uuid=vonage_answer_request.uuid,
                    transcriber_config=self.transcriber_config,
                    synthesizer_config=self.synthesizer_config,
                    vonage_config=self.vonage_config,
                ).dict(),
            )
            assert response.ok, response.text
            return Response(
                response.text,
                media_type="application/json",
            )

        async def handle_twilio_call(
            twilio_sid: str = Form(alias="CallSid"),
            twilio_from: str = Form(alias="From"),
            twilio_to: str = Form(alias="To"),
        ) -> Response:
            response = requests.post(
                self.vocode_inbound_call_url,
                headers={"Authorization": f"Bearer {vocode.api_key}"},
                json=CreateInboundCall(
                    recipient=CallEntity(
                        phone_number=twilio_to,
                    ),
                    caller=CallEntity(phone_number=twilio_from),
                    agent_config=self.agent_config,
                    twilio_sid=twilio_sid,
                    transcriber_config=self.transcriber_config,
                    synthesizer_config=self.synthesizer_config,
                    twilio_config=self.twilio_config,
                ).dict(),
            )
            if response.status_code == 429:
                return Response(
                    f"<Response><Say>{self.response_on_rate_limit}</Say></Response>",
                    media_type="application/xml",
                )
            assert response.ok, response.text
            return Response(
                response.text,
                media_type="application/xml",
            )

        if self.vonage_config:
            self.app.post("/vocode")(handle_vonage_call)
        elif self.twilio_config:
            self.app.post("/vocode")(handle_twilio_call)
        else:
            raise ValueError("Must provide vonage_config or twilio_config")

    def run(self, host="localhost", port=3000):
        uvicorn.run(self.app, host=host, port=port)
