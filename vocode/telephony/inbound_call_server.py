from fastapi import FastAPI, Response, Form
from typing import Optional
import requests
import uvicorn
from vocode.models.synthesizer import SynthesizerConfig
from twilio.jwt.access_token.grants import VoiceGrant

from vocode.models.transcriber import TranscriberConfig
from .. import api_key, BASE_URL

from ..models.agent import AgentConfig
from ..models.telephony import CreateInboundCall, TwilioConfig, TwilioConfig

VOCODE_INBOUND_CALL_URL = f"https://{BASE_URL}/create_inbound_call"


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

    async def handle_call(self, twilio_sid: str = Form(alias="CallSid")):
        response = requests.post(
            VOCODE_INBOUND_CALL_URL,
            headers={"Authorization": f"Bearer {api_key}"},
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
