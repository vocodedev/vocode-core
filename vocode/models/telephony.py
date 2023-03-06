from typing import Optional
from vocode.models.model import BaseModel
from vocode.models.agent import AgentConfig
from vocode.models.synthesizer import SynthesizerConfig


class CallEntity(BaseModel):
    phone_number: str


class CreateInboundCall(BaseModel):
    agent_config: AgentConfig
    twilio_sid: str


class CreateOutboundCall(BaseModel):
    recipient: CallEntity
    caller: CallEntity
    agent_config: AgentConfig
    synthesizer_config: Optional[SynthesizerConfig] = None
    # TODO add IVR/etc.
