from fastapi import FastAPI, Response
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
    ):
        self.agent_config = agent_config
        self.transcriber_config = transcriber_config
        self.synthesizer_config = synthesizer_config
        self.app = FastAPI()

        self.vonage_config = vonage_config
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

        self.app.post("/vocode")(handle_vonage_call)

    def run(self, host="localhost", port=3000):
        uvicorn.run(self.app, host=host, port=port)
