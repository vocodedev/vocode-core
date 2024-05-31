from typing import Dict, Optional

from loguru import logger

from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.models.telephony import (
    TelephonyConfig,
    TwilioCallConfig,
    TwilioConfig,
    VonageCallConfig,
    VonageConfig,
)
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.telephony.client.abstract_telephony_client import AbstractTelephonyClient
from vocode.streaming.telephony.client.twilio_client import TwilioClient
from vocode.streaming.telephony.client.vonage_client import VonageClient
from vocode.streaming.telephony.config_manager.base_config_manager import BaseConfigManager
from vocode.streaming.utils import create_conversation_id


class OutboundCall:
    def __init__(
        self,
        base_url: str,
        to_phone: str,
        from_phone: str,
        config_manager: BaseConfigManager,
        agent_config: AgentConfig,
        telephony_config: TelephonyConfig,
        telephony_params: Optional[Dict[str, str]] = None,
        transcriber_config: Optional[TranscriberConfig] = None,
        synthesizer_config: Optional[SynthesizerConfig] = None,
        conversation_id: Optional[str] = None,
        sentry_tags: Dict[str, str] = {},
        digits: Optional[
            str
        ] = None,  # Keys to press when the call connects, see send_digits https://www.twilio.com/docs/voice/api/call-resource#create-a-call-resource
        output_to_speaker: bool = False,
    ):
        self.base_url = base_url
        self.to_phone = to_phone
        self.from_phone = from_phone
        self.config_manager = config_manager
        self.agent_config = agent_config
        self.conversation_id = conversation_id or create_conversation_id()
        self.telephony_config = telephony_config
        self.telephony_params = telephony_params or {}
        self.telephony_client = self.create_telephony_client()
        self.transcriber_config = self.create_transcriber_config(transcriber_config)
        self.synthesizer_config = self.create_synthesizer_config(synthesizer_config)
        self.output_to_speaker = output_to_speaker
        self.sentry_tags = sentry_tags
        self.digits = digits

    def create_telephony_client(self) -> AbstractTelephonyClient:
        if isinstance(self.telephony_config, TwilioConfig):
            return TwilioClient(base_url=self.base_url, maybe_twilio_config=self.telephony_config)
        elif isinstance(self.telephony_config, VonageConfig):
            return VonageClient(base_url=self.base_url, maybe_vonage_config=self.telephony_config)

    def create_transcriber_config(
        self, transcriber_config_override: Optional[TranscriberConfig]
    ) -> TranscriberConfig:
        if transcriber_config_override is not None:
            return transcriber_config_override
        if isinstance(self.telephony_config, TwilioConfig):
            return TwilioCallConfig.default_transcriber_config()
        elif isinstance(self.telephony_config, VonageConfig):
            return VonageCallConfig.default_transcriber_config()
        else:
            raise ValueError("No telephony config provided")

    def create_synthesizer_config(
        self, synthesizer_config_override: Optional[SynthesizerConfig]
    ) -> SynthesizerConfig:
        if synthesizer_config_override is not None:
            return synthesizer_config_override
        if isinstance(self.telephony_config, TwilioConfig):
            return TwilioCallConfig.default_synthesizer_config()
        elif isinstance(self.telephony_config, VonageConfig):
            return VonageCallConfig.default_synthesizer_config()
        else:
            raise ValueError("No telephony config provided")

    async def start(self):
        logger.debug("Starting outbound call")
        self.telephony_id = await self.telephony_client.create_call(
            conversation_id=self.conversation_id,
            to_phone=self.to_phone,
            from_phone=self.from_phone,
            record=self.telephony_client.get_telephony_config().record,  # note twilio does not use this
            telephony_params=self.telephony_params,
            digits=self.digits,
        )
        if isinstance(self.telephony_client, TwilioClient):
            call_config = TwilioCallConfig(
                transcriber_config=self.transcriber_config,
                agent_config=self.agent_config,
                synthesizer_config=self.synthesizer_config,
                twilio_config=self.telephony_client.twilio_config,
                twilio_sid=self.telephony_id,
                from_phone=self.from_phone,
                to_phone=self.to_phone,
                sentry_tags=self.sentry_tags,
                telephony_params=self.telephony_params,
                direction="outbound",
            )
        elif isinstance(self.telephony_client, VonageClient):
            call_config = VonageCallConfig(
                transcriber_config=self.transcriber_config,
                agent_config=self.agent_config,
                synthesizer_config=self.synthesizer_config,
                vonage_config=self.telephony_client.vonage_config,
                vonage_uuid=self.telephony_id,
                from_phone=self.from_phone,
                to_phone=self.to_phone,
                output_to_speaker=False,
                sentry_tags=self.sentry_tags,
                telephony_params=self.telephony_params,
                direction="outbound",
            )
        else:
            raise ValueError("Unknown telephony client")
        await self.config_manager.save_config(self.conversation_id, call_config)

    async def end(self):
        return await self.telephony_client.end_call(self.telephony_id)
