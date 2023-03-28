import logging
from typing import Optional
from twilio.rest import Client
from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.models.telephony import CallConfig, TwilioConfig
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)
from vocode.streaming.telephony.conversation.outbound_call import OutboundCall
from vocode.streaming.transcriber.base_transcriber import BaseTranscriber
from vocode.streaming.utils import create_conversation_id


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
        transcriber_config: TranscriberConfig,
        synthesizer_config: SynthesizerConfig,
        twilio_config: Optional[TwilioConfig] = None,
        conversation_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(
            base_url=base_url,
            to_phone=zoom_number,
            from_phone=from_phone,
            config_manager=config_manager,
            transcriber_config=transcriber_config,
            agent_config=agent_config,
            synthesizer_config=synthesizer_config,
            twilio_config=twilio_config,
            conversation_id=conversation_id,
            logger=logger,
        )
        self.zoom_number = zoom_number
        self.zoom_meeting_id = zoom_meeting_id
        self.zoom_meeting_password = zoom_meeting_password
        self.from_phone = from_phone

    def start(self):
        self.validate_outbound_call(
            self.zoom_number,
            self.from_phone,
            mobile_only=False,
        )
        digits = f"ww{self.zoom_meeting_id}#"
        if self.zoom_meeting_password:
            digits += f"wwww*{self.zoom_meeting_password}#"
        self.logger.debug("Sending digits %s to the call", digits)
        twilio_sid = self.create_twilio_call(
            self.zoom_number,
            self.from_phone,
            digits=digits,
        )
        call_config = CallConfig(
            transcriber_config=self.transcriber_config,
            agent_config=self.agent_config,
            synthesizer_config=self.synthesizer_config,
            twilio_config=self.twilio_config,
            twilio_sid=twilio_sid,
        )
        self.config_manager.save_config(self.conversation_id, call_config)
