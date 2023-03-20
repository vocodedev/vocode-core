from fastapi import FastAPI, Response, Form
from typing import Optional
import requests
import uvicorn

import vocode
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.telephony import (
    CreateInboundCall,
    TwilioConfig,
    TwilioConfig,
)


class InboundCallServer:
    def __init__(
        self,
        agent_config: AgentConfig,
        transcriber_config: Optional[TranscriberConfig] = None,
        synthesizer_config: Optional[SynthesizerConfig] = None,
        response_on_rate_limit: Optional[str] = None,
        twilio_config: Optional[TwilioConfig] = None,
    ):
        self.agent_config = agent_config
        self.transcriber_config = transcriber_config
        self.synthesizer_config = synthesizer_config
        self.app = FastAPI()
        self.app.post("/vocode")(self.handle_call)
        self.response_on_rate_limit = (
            response_on_rate_limit
            or "The line is really busy right now, check back later!"
        )
        self.twilio_config = twilio_config
        self.vocode_inbound_call_url = f"https://{vocode.base_url}/create_inbound_call"

    async def handle_call(self, twilio_sid: str = Form(alias="CallSid")):
        response = requests.post(
            self.vocode_inbound_call_url,
            headers={"Authorization": f"Bearer {vocode.api_key}"},
            json=CreateInboundCall(
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

    def run(self, host="localhost", port=3000):
        uvicorn.run(self.app, host=host, port=port)
