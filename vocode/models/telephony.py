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
    conversation_id: Optional[str] = None


class CreateOutboundCall(BaseModel):
    recipient: CallEntity
    caller: CallEntity
    transcriber_config: Optional[TranscriberConfig] = None
    agent_config: AgentConfig
    synthesizer_config: Optional[SynthesizerConfig] = None
    conversation_id: Optional[str] = None
    # TODO add IVR/etc.
