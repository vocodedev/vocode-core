from typing import Optional
from vocode.models.agent import AgentConfig
from vocode.models.synthesizer import SynthesizerConfig
from vocode.models.transcriber import TranscriberConfig
from ..models.telephony import CallEntity, CreateOutboundCall
import requests
from .. import api_key, BASE_URL

VOCODE_OUTBOUND_CALL_URL = f"https://{BASE_URL}/create_outbound_call"


class OutboundCall:
    def __init__(
        self,
        recipient: CallEntity,
        caller: CallEntity,
        agent_config: AgentConfig,
        transcriber_config: Optional[TranscriberConfig] = None,
        synthesizer_config: Optional[SynthesizerConfig] = None,
    ):
        self.recipient = recipient
        self.caller = caller
        self.agent_config = agent_config
        self.transcriber_config = transcriber_config
        self.synthesizer_config = synthesizer_config

    def start(self):
        return requests.post(
            VOCODE_OUTBOUND_CALL_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=CreateOutboundCall(
                recipient=self.recipient,
                caller=self.caller,
                agent_config=self.agent_config,
                transcriber_config=self.transcriber_config,
                synthesizer_config=self.synthesizer_config,
            ).dict(),
        )
