from abc import ABC
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel

from vocode.streaming.models.adaptive_object import AdaptiveObject
from vocode.streaming.models.agent import AgentConfig


class WebSocketAgentMessage(AdaptiveObject, ABC):
    type: Any
    conversation_id: Optional[str] = None


class WebSocketAgentTextMessage(WebSocketAgentMessage):
    type: Literal["websocket_agent_text"] = "websocket_agent_text"

    class Payload(BaseModel):
        text: str

    data: Payload

    @classmethod
    def from_text(cls, text: str, conversation_id: Optional[str] = None):
        return cls(data=cls.Payload(text=text), conversation_id=conversation_id)


class WebSocketAgentStopMessage(WebSocketAgentMessage):
    type: Literal["websocket_agent_stop"] = "websocket_agent_stop"


class WebSocketUserImplementedAgentConfig(AgentConfig):
    class RouteConfig(BaseModel):
        url: str

    type: Literal["agent_websocket_user_implemented"] = "agent_websocket_user_implemented"
    respond: RouteConfig
