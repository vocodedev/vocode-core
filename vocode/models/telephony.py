from vocode.models.model import BaseModel
from vocode.models.agent import AgentConfig, InformationRetrievalAgentConfig

class CallEntity(BaseModel):
    phone_number: str

class CreateCallRequest(BaseModel):
    recipient: CallEntity
    caller: CallEntity
    agent_config: AgentConfig
    # TODO add IVR/etc.
