from typing import Optional
from vocode.models.agent import AgentConfig
from vocode.models.synthesizer import SynthesizerConfig
from vocode.models.transcriber import TranscriberConfig
from vocode.telephony.utils import create_access_token
from ..models.telephony import (
    CallEntity,
    CreateOutboundCall,
    EndOutboundCall,
    InternalTwilioConfig,
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
        internal_twilio_config: Optional[InternalTwilioConfig] = None,
    ):
        self.recipient = recipient
        self.caller = caller
        self.agent_config = agent_config
        self.transcriber_config = transcriber_config
        self.synthesizer_config = synthesizer_config
        self.conversation_id = conversation_id
        self.internal_twilio_config = internal_twilio_config

    def create_twilio_config(self) -> TwilioConfig:
        access_token = create_access_token(self.internal_twilio_config)
        access_token.add_grant(
            VoiceGrant(
                outgoing_application_sid=self.internal_twilio_config.outgoing_application_sid
            )
        )
        return TwilioConfig(
            account_sid=self.internal_twilio_config.account_sid,
            access_token=access_token.to_jwt(),
        )

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
                twilio_config=self.create_twilio_config()
                if self.internal_twilio_config
                else None,
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
            ).dict(),
        )
        assert response.ok, response.text
