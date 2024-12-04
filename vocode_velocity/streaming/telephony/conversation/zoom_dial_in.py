from typing import Optional

from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.telephony.config_manager.base_config_manager import BaseConfigManager
from vocode.streaming.telephony.conversation.outbound_call import OutboundCall


class ZoomDialIn(OutboundCall):
    def __init__(
        self,
        base_url: str,
        zoom_number: str,
        zoom_meeting_id: str,
        zoom_meeting_password: Optional[str],
        from_phone: str,
        config_manager: BaseConfigManager,
        agent_config: AgentConfig,
        twilio_config: TwilioConfig,
        transcriber_config: Optional[TranscriberConfig] = None,
        synthesizer_config: Optional[SynthesizerConfig] = None,
        conversation_id: Optional[str] = None,
    ):
        digits = f"wwww{zoom_meeting_id}#"
        if zoom_meeting_password:
            digits += f"wwwwwwww*{zoom_meeting_password}#"

        super().__init__(
            base_url=base_url,
            to_phone=zoom_number,
            from_phone=from_phone,
            config_manager=config_manager,
            transcriber_config=transcriber_config,
            agent_config=agent_config,
            synthesizer_config=synthesizer_config,
            telephony_config=twilio_config,
            conversation_id=conversation_id,
            digits=digits,
        )

        self.zoom_number = zoom_number
        self.zoom_meeting_id = zoom_meeting_id
        self.zoom_meeting_password = zoom_meeting_password
