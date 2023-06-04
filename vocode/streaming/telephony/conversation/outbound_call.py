import logging
from typing import Optional
from vocode import getenv

from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.synthesizer import (
    AzureSynthesizerConfig,
    SynthesizerConfig,
)
from vocode.streaming.models.telephony import CallConfig, TwilioConfig
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
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
        self.transcriber_config = transcriber_config or DeepgramTranscriberConfig(
            sampling_rate=16000,
            audio_encoding=AudioEncoding.LINEAR16,
            chunk_size=DEFAULT_CHUNK_SIZE,
            model="phonecall",
            tier="nova",
            endpointing_config=PunctuationEndpointingConfig(),
        )
        self.synthesizer_config = synthesizer_config or AzureSynthesizerConfig(
            sampling_rate=16000, audio_encoding=AudioEncoding.LINEAR16
        )
        self.conversation_id = conversation_id or create_conversation_id()
        self.logger = logger or logging.getLogger(__name__)
        self.twilio_config = twilio_config or TwilioConfig(
            account_sid=getenv("TWILIO_ACCOUNT_SID"),
            auth_token=getenv("TWILIO_AUTH_TOKEN"),
        )
        # self.telephony_client = TwilioClient(
        #     base_url=base_url, twilio_config=self.twilio_config
        # )
        self.telephony_client = VonageClient(base_url=base_url)
        self.twilio_sid = None

    def start(self):
        self.logger.debug("Starting outbound call")
        self.telephony_client.validate_outbound_call(
            to_phone=self.to_phone,
            from_phone=self.from_phone,
            mobile_only=self.mobile_only,
        )
        self.twilio_sid = self.telephony_client.create_call(
            conversation_id=self.conversation_id,
            to_phone=self.to_phone,
            from_phone=self.from_phone,
            record=self.twilio_config.record,
            digits=self.digits,
        )
        call_config = CallConfig(
            transcriber_config=self.transcriber_config,
            agent_config=self.agent_config,
            synthesizer_config=self.synthesizer_config,
            twilio_config=self.twilio_config,
            twilio_sid=self.twilio_sid,
            twilio_from=self.from_phone,
            twilio_to=self.to_phone,
        )
        self.config_manager.save_config(self.conversation_id, call_config)

    def end(self):
        return self.telephony_client.end_call(self.twilio_sid)
