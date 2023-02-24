from pydantic import BaseModel
from vocode.models.agent import AgentConfig, InformationRetrievalAgentConfig


class CallEntity(BaseModel):
    phone_number: str
    descriptor: str


class CreateCallRequest(BaseModel):
    recipient: CallEntity
    caller: CallEntity
    agent_config: InformationRetrievalAgentConfig  # TODO switch to AgentConfig
    # TODO add IVR/etc.
