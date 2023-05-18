from typing import Optional
import requests

import vocode
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.telephony.hosted.exceptions import RateLimitExceeded
from vocode.streaming.telephony.hosted.outbound_call import OutboundCall
from vocode.streaming.models.telephony import (
    CallEntity,
    DialIntoZoomCall,
    TwilioConfig,
)


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
        self.vocode_zoom_dial_in_url = f"https://{vocode.base_url}/dial_into_zoom_call"

    def start(self):
        response = requests.post(
            self.vocode_zoom_dial_in_url,
            headers={"Authorization": f"Bearer {vocode.api_key}"},
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
        if not response.ok:
            if response.status_code == 429:
                raise RateLimitExceeded("Too many requests")
            else:
                raise Exception(response.text)
        data = response.json()
        self.conversation_id = data["id"]
