from fastapi import FastAPI, Response, Form
from typing import Optional
import requests
import uvicorn
from .. import api_key, BASE_URL

from ..models.agent import AgentConfig
from ..models.telephony import CreateInboundCall

VOCODE_INBOUND_CALL_URL = f"https://{BASE_URL}/create_inbound_call"


class InboundCallServer:
    def __init__(
        self, agent_config: AgentConfig, response_on_rate_limit: Optional[str] = None
    ):
        self.agent_config = agent_config
        self.app = FastAPI()
        self.app.post("/vocode")(self.handle_call)
        self.response_on_rate_limit = (
            response_on_rate_limit
            or "The line is really busy right now, check back later!"
        )

    async def handle_call(self, twilio_sid: str = Form(alias="CallSid")):
        response = requests.post(
            VOCODE_INBOUND_CALL_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=CreateInboundCall(
                agent_config=self.agent_config, twilio_sid=twilio_sid
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
