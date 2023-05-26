from enum import Enum
from typing import Optional
from vocode.streaming.models.agent import AgentConfig, AgentType

from vocode.streaming.models.model import BaseModel, TypedModel


class WebSocketAgentMessageType(str, Enum):
    BASE = "websocket_agent_base"
    TEXT = "websocket_agent_text"
    STOP = "websocket_agent_stop"


class WebSocketAgentMessage(TypedModel, type=WebSocketAgentMessageType.BASE):
    conversation_id: Optional[str] = None

    # TODO: Find a better way to serialize this to JSON
    def to_json_dictionary(self) -> dict:
        return {
            "type": self.type,
            "conversation_id": self.conversation_id,
        }


class WebSocketAgentTextMessage(
    WebSocketAgentMessage, type=WebSocketAgentMessageType.TEXT
):
    class Payload(BaseModel):
        text: str

    data: Payload

    def to_json_dictionary(self) -> dict:
        properties = super().to_json_dictionary()
        properties["data"] = {
            "text": self.data.text,
        }
        return properties

    @classmethod
    def from_text(cls, text: str, conversation_id: Optional[str] = None):
        return cls(data=cls.Payload(text=text), conversation_id=conversation_id)


class WebSocketAgentStopMessage(
    WebSocketAgentMessage, type=WebSocketAgentMessageType.STOP
):
    pass


class WebSocketUserImplementedAgentConfig(
    AgentConfig, type=AgentType.WEBSOCKET_USER_IMPLEMENTED.value
):
    class RouteConfig(BaseModel):
        url: str

    respond: RouteConfig
