from typing import Optional
from vocode.models.model import BaseModel
from vocode.models.agent import AgentConfig
from vocode.models.synthesizer import SynthesizerConfig
from vocode.models.transcriber import TranscriberConfig


class CallEntity(BaseModel):
    phone_number: str


class CreateInboundCall(BaseModel):
    transcriber_config: Optional[TranscriberConfig] = None
    agent_config: AgentConfig
    synthesizer_config: Optional[SynthesizerConfig] = None
    twilio_sid: str


class EndOutboundCall(BaseModel):
    call_id: str


class CreateOutboundCall(BaseModel):
    recipient: CallEntity
    caller: CallEntity
    transcriber_config: Optional[TranscriberConfig] = None
    agent_config: AgentConfig
    synthesizer_config: Optional[SynthesizerConfig] = None
    conversation_id: Optional[str] = None
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
