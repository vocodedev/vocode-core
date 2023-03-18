from typing import Optional
from vocode.models.agent import AgentConfig
from vocode.models.synthesizer import SynthesizerConfig
from vocode.models.transcriber import TranscriberConfig
from vocode.telephony.outbound_call import OutboundCall
from ..models.telephony import (
    CallEntity,
    DialIntoZoomCall,
    TwilioConfig,
)
import requests
from .. import api_key, BASE_URL

VOCODE_ZOOM_DIAL_IN_URL = f"https://{BASE_URL}/dial_into_zoom_call"


class ZoomDialIn(OutboundCall):
    def __init__(
        self,
        recipient: CallEntity,
        caller: CallEntity,
        zoom_meeting_id: str,
        zoom_meeting_password: str,
        agent_config: AgentConfig,
        transcriber_config: Optional[TranscriberConfig] = None,
        synthesizer_config: Optional[SynthesizerConfig] = None,
        conversation_id: Optional[str] = None,
        twilio_config: Optional[TwilioConfig] = None,
    ):
        super().__init__(
            recipient=recipient,
            caller=caller,
            agent_config=agent_config,
            transcriber_config=transcriber_config,
            synthesizer_config=synthesizer_config,
            conversation_id=conversation_id,
            twilio_config=twilio_config,
        )
        self.zoom_meeting_id = zoom_meeting_id
        self.zoom_meeting_password = zoom_meeting_password

    def start(self) -> str:
        response = requests.post(
            VOCODE_ZOOM_DIAL_IN_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=DialIntoZoomCall(
                recipient=self.recipient,
                caller=self.caller,
                zoom_meeting_id=self.zoom_meeting_id,
                zoom_meeting_password=self.zoom_meeting_password,
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
