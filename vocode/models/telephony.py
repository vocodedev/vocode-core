from vocode.models.model import BaseModel
from vocode.models.agent import AgentConfig

class CallEntity(BaseModel):
    phone_number: str

class CreateInboundCall(BaseModel):
    agent_config: AgentConfig
    twilio_sid: str

class CreateOutboundCall(BaseModel):
    recipient: CallEntity
    caller: CallEntity
    agent_config: AgentConfig 
    # TODO add IVR/etc.
