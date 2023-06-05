import logging
from typing import Optional, Union
from vocode import getenv

from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.synthesizer import (
    SynthesizerConfig,
)
from vocode.streaming.models.telephony import (
    TwilioCallConfig,
    TwilioConfig,
    VonageCallConfig,
    VonageConfig,
)
from vocode.streaming.models.transcriber import (
    TranscriberConfig,
)
from vocode.streaming.telephony.client.twilio_client import TwilioClient
from vocode.streaming.telephony.client.vonage_client import VonageClient
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)
from vocode.streaming.telephony.constants import (
    DEFAULT_AUDIO_ENCODING,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_SAMPLING_RATE,
    VONAGE_AUDIO_ENCODING,
    VONAGE_CHUNK_SIZE,
    VONAGE_SAMPLING_RATE,
)
from vocode.streaming.utils import create_conversation_id


class OutboundCall:
    def __init__(
        self,
        base_url: str,
        to_phone: str,
        from_phone: str,
        config_manager: BaseConfigManager,
        agent_config: AgentConfig,
        twilio_config: Optional[TwilioConfig] = None,
        vonage_config: Optional[VonageConfig] = None,
        transcriber_config: Optional[TranscriberConfig] = None,
        synthesizer_config: Optional[SynthesizerConfig] = None,
        conversation_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        mobile_only: bool = True,
        digits: Optional[
            str
        ] = None,  # Keys to press when the call connects, see send_digits https://www.twilio.com/docs/voice/api/call-resource#create-a-call-resource
    ):
        self.base_url = base_url
        self.to_phone = to_phone
        self.digits = digits
        self.from_phone = from_phone
        self.mobile_only = mobile_only
        self.config_manager = config_manager
        self.agent_config = agent_config
        self.conversation_id = conversation_id or create_conversation_id()
        self.logger = logger or logging.getLogger(__name__)
        if not twilio_config and not vonage_config:
            self.logger.debug(
                "No telephony config provided, defaulting to Twilio env vars"
            )
            twilio_config = TwilioConfig(
                account_sid=getenv("TWILIO_ACCOUNT_SID"),
                auth_token=getenv("TWILIO_AUTH_TOKEN"),
            )
        self.telephony_client: Union[TwilioClient, VonageClient]
        if twilio_config:
            self.telephony_client = TwilioClient(
                base_url=base_url, twilio_config=twilio_config
            )
            self.transcriber_config = (
                transcriber_config or TwilioCallConfig.default_transcriber_config()
            )
            self.synthesizer_config = (
                synthesizer_config or TwilioCallConfig.default_synthesizer_config()
            )
        elif vonage_config:
            self.telephony_client = VonageClient(
                base_url=base_url, vonage_config=vonage_config
            )
            self.transcriber_config = (
                transcriber_config or VonageCallConfig.default_transcriber_config()
            )
            self.synthesizer_config = (
                synthesizer_config or VonageCallConfig.default_synthesizer_config()
            )
        self.telephony_id = None

    def start(self):
        self.logger.debug("Starting outbound call")
        self.telephony_client.validate_outbound_call(
            to_phone=self.to_phone,
            from_phone=self.from_phone,
            mobile_only=self.mobile_only,
        )
        self.telephony_id = self.telephony_client.create_call(
            conversation_id=self.conversation_id,
            to_phone=self.to_phone,
            from_phone=self.from_phone,
            record=self.telephony_client.get_telephony_config().record,
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
            )
        else:
            raise ValueError("Unknown telephony client")
        self.config_manager.save_config(self.conversation_id, call_config)

    def end(self):
        return self.telephony_client.end_call(self.telephony_id)
