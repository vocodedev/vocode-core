from enum import Enum
from typing import Optional
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.model import BaseModel, TypedModel
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.models.transcriber import TranscriberConfig


class TwilioConfig(BaseModel):
    account_sid: str
    auth_token: str
    record: bool = False


class VonageConfig(BaseModel):
    api_key: str
    api_secret: str
    application_id: str
    private_key: str
    record: bool = False


class CallEntity(BaseModel):
    phone_number: str


class CreateInboundCall(BaseModel):
    transcriber_config: Optional[TranscriberConfig] = None
    agent_config: AgentConfig
    synthesizer_config: Optional[SynthesizerConfig] = None
    twilio_sid: str
    conversation_id: Optional[str] = None
    twilio_config: Optional[TwilioConfig] = None


class EndOutboundCall(BaseModel):
    call_id: str
    twilio_config: Optional[TwilioConfig] = None


class CreateOutboundCall(BaseModel):
    recipient: CallEntity
    caller: CallEntity
    transcriber_config: Optional[TranscriberConfig] = None
    agent_config: AgentConfig
    synthesizer_config: Optional[SynthesizerConfig] = None
    conversation_id: Optional[str] = None
    twilio_config: Optional[TwilioConfig] = None
    # TODO add IVR/etc.


class DialIntoZoomCall(BaseModel):
    recipient: CallEntity
    caller: CallEntity
    zoom_meeting_id: str
    zoom_meeting_password: Optional[str]
    transcriber_config: Optional[TranscriberConfig] = None
    agent_config: AgentConfig
    synthesizer_config: Optional[SynthesizerConfig] = None
    conversation_id: Optional[str] = None
    twilio_config: Optional[TwilioConfig] = None


class CallConfigType(str, Enum):
    BASE = "call_config_base"
    TWILIO = "call_config_twilio"
    VONAGE = "call_config_vonage"


class CallConfig(TypedModel, type=CallConfigType.BASE.value):
    transcriber_config: TranscriberConfig
    agent_config: AgentConfig
    synthesizer_config: SynthesizerConfig
    from_phone: str
    to_phone: str


class TwilioCallConfig(CallConfig, type=CallConfigType.TWILIO.value):
    twilio_config: TwilioConfig
    twilio_sid: str


class VonageCallConfig(CallConfig, type=CallConfigType.VONAGE.value):
    vonage_config: VonageConfig
    vonage_uuid: str
