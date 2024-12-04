from enum import Enum
from typing import Optional

from vocode.streaming.models.agent import AgentConfig, AgentType
from vocode.streaming.models.model import BaseModel, TypedModel


class WebSocketAgentMessageType(str, Enum):
    BASE = "websocket_agent_base"
    TEXT = "websocket_agent_text"
    STOP = "websocket_agent_stop"


class WebSocketAgentMessage(TypedModel, type=WebSocketAgentMessageType.BASE):  # type: ignore
    conversation_id: Optional[str] = None


class WebSocketAgentTextMessage(
    WebSocketAgentMessage, type=WebSocketAgentMessageType.TEXT  # type: ignore
):
    class Payload(BaseModel):
        text: str

    data: Payload

    @classmethod
    def from_text(cls, text: str, conversation_id: Optional[str] = None):
        return cls(data=cls.Payload(text=text), conversation_id=conversation_id)


class WebSocketAgentStopMessage(
    WebSocketAgentMessage, type=WebSocketAgentMessageType.STOP  # type: ignore
):
    pass


class WebSocketUserImplementedAgentConfig(
    AgentConfig, type=AgentType.WEBSOCKET_USER_IMPLEMENTED.value  # type: ignore
):
    class RouteConfig(BaseModel):
        url: str

    respond: RouteConfig
