from typing import Optional
from vocode.models.agent import AgentConfig
from vocode.models.synthesizer import SynthesizerConfig
from vocode.models.transcriber import TranscriberConfig
from ..models.telephony import (
    CallEntity,
    CreateOutboundCall,
    EndOutboundCall,
    TwilioConfig,
)
import requests
from .. import api_key, BASE_URL

from twilio.jwt.access_token.grants import VoiceGrant


VOCODE_CREATE_OUTBOUND_CALL_URL = f"https://{BASE_URL}/create_outbound_call"
VOCODE_END_OUTBOUND_CALL_URL = f"https://{BASE_URL}/end_outbound_call"


class OutboundCall:
    def __init__(
        self,
        recipient: CallEntity,
        caller: CallEntity,
        agent_config: AgentConfig,
        transcriber_config: Optional[TranscriberConfig] = None,
        synthesizer_config: Optional[SynthesizerConfig] = None,
        conversation_id: Optional[str] = None,
        twilio_config: Optional[TwilioConfig] = None,
    ):
        self.recipient = recipient
        self.caller = caller
        self.agent_config = agent_config
        self.transcriber_config = transcriber_config
        self.synthesizer_config = synthesizer_config
        self.conversation_id = conversation_id
        self.twilio_config = twilio_config

    def start(self) -> str:
        response = requests.post(
            VOCODE_CREATE_OUTBOUND_CALL_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=CreateOutboundCall(
                recipient=self.recipient,
                caller=self.caller,
                agent_config=self.agent_config,
                transcriber_config=self.transcriber_config,
                synthesizer_config=self.synthesizer_config,
                conversation_id=self.conversation_id,
                twilio_config=self.twilio_config,
            ).dict(),
        )
        assert response.ok, response.text
        data = response.json()
        self.conversation_id = data["id"]

    def end(self) -> str:
        response = requests.post(
            VOCODE_END_OUTBOUND_CALL_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=EndOutboundCall(
                call_id=self.conversation_id,
                twilio_config=self.twilio_config,
            ).dict(),
        )
        assert response.ok or response.status_code == 404, response.text
