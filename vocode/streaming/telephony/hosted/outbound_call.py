from typing import Optional
import requests

import vocode
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.models.telephony import (
    CallEntity,
    CreateOutboundCall,
    EndOutboundCall,
    TwilioConfig,
    VonageConfig,
)
from vocode.streaming.telephony.hosted.exceptions import RateLimitExceeded


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
        vonage_config: Optional[VonageConfig] = None,
    ):
        self.recipient = recipient
        self.caller = caller
        self.agent_config = agent_config
        self.transcriber_config = transcriber_config
        self.synthesizer_config = synthesizer_config
        self.conversation_id = conversation_id
        self.twilio_config = twilio_config
        self.vonage_config = vonage_config
        self.vocode_create_outbound_call_url = (
            f"https://{vocode.base_url}/create_outbound_call"
        )
        self.vocode_end_outbound_call_url = (
            f"https://{vocode.base_url}/end_outbound_call"
        )

    def start(self):
        try:
            response = requests.post(
                self.vocode_create_outbound_call_url,
                headers={"Authorization": f"Bearer {vocode.api_key}"},
                json=CreateOutboundCall(
                    recipient=self.recipient,
                    caller=self.caller,
                    agent_config=self.agent_config,
                    transcriber_config=self.transcriber_config,
                    synthesizer_config=self.synthesizer_config,
                    conversation_id=self.conversation_id,
                    twilio_config=self.twilio_config,
                    vonage_config=self.vonage_config,
                ).dict(),
                timeout=5,
            )
            if not response.ok:
                if response.status_code == 429:
                    raise RateLimitExceeded("Too many requests")
                else:
                    raise Exception(response.text)
            data = response.json()
            self.conversation_id = data["id"]
        except requests.exceptions.Timeout:
            raise RateLimitExceeded("Timed out")

    def end(self):
        try:
            response = requests.post(
                self.vocode_end_outbound_call_url,
                headers={"Authorization": f"Bearer {vocode.api_key}"},
                json=EndOutboundCall(
                    call_id=self.conversation_id,
                    twilio_config=self.twilio_config,
                    vonage_config=self.vonage_config,
                ).dict(),
                timeout=2,
            )
            assert response.ok or response.status_code == 404, response.text
        except requests.exceptions.Timeout:
            raise RateLimitExceeded("Timed out")
