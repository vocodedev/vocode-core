from typing import Optional
from enum import Enum
from .model import TypedModel, BaseModel


class AgentType(str, Enum):
    BASE = "base"
    LLM = "llm"
    CHAT_GPT = "chat_gpt"
    ECHO = "echo"
    INFORMATION_RETRIEVAL = "information_retrieval"
    RESTFUL_USER_IMPLEMENTED = "restful_user_implemented"
    WEBSOCKET_USER_IMPLEMENTED = "websocket_user_implemented"


class AgentConfig(TypedModel, type=AgentType.BASE):
    initial_message: Optional[str] = None
    generate_responses: bool = True

class LLMAgentConfig(AgentConfig, type=AgentType.LLM):
    prompt_preamble: str
    expected_first_prompt: Optional[str] = None

class ChatGPTAgentConfig(AgentConfig, type=AgentType.CHAT_GPT):
    prompt_preamble: str
    expected_first_prompt: Optional[str] = None

class InformationRetrievalAgentConfig(
    AgentConfig, type=AgentType.INFORMATION_RETRIEVAL
):
    recipient_descriptor: str
    caller_descriptor: str
    goal_description: str
    fields: list[str]
    # TODO: add fields for IVR, voicemail


class EchoAgentConfig(AgentConfig, type=AgentType.ECHO):
    pass

class RESTfulUserImplementedAgentConfig(AgentConfig, type=AgentType.RESTFUL_USER_IMPLEMENTED):
    class EndpointConfig(BaseModel):
        url: str
        method: str = "POST"

    respond: EndpointConfig
    generate_responses: bool = False
    # generate_response: Optional[EndpointConfig]
    # update_last_bot_message_on_cut_off: Optional[EndpointConfig]

class RESTfulAgentInput(BaseModel):
    human_input: str

class RESTfulAgentOutput(BaseModel):
    response: str

class WebSocketUserImplementedAgentConfig(AgentConfig, type=AgentType.WEBSOCKET_USER_IMPLEMENTED):
    class RouteConfig(BaseModel):
        url: str

    respond: RouteConfig
    generate_responses: bool = False
    # generate_response: Optional[RouteConfig]
    # send_message_on_cut_off: bool = False

class WebSocketAgentMessageType(str, Enum):
    AGENT_BASE = 'agent_base'
    AGENT_START = 'agent_start'
    AGENT_TEXT = 'agent_text'
    AGENT_READY = 'agent_ready'
    AGENT_STOP = 'agent_stop'

class WebSocketAgentMessage(TypedModel, type=WebSocketAgentMessageType.AGENT_BASE): pass

class AgentTextMessage(WebSocketAgentMessage, type=WebSocketAgentMessageType.AGENT_TEXT):
    class Payload(BaseModel):
        text: str

    data: Payload

    @classmethod
    def from_text(cls, text: str):
        return cls(data=cls.Payload(text=text))


class AgentStartMessage(WebSocketAgentMessage, type=WebSocketAgentMessageType.AGENT_START):
    pass

class AgentReadyMessage(WebSocketAgentMessage, type=WebSocketAgentMessageType.AGENT_READY):
    pass

class AgentStopMessage(WebSocketAgentMessage, type=WebSocketAgentMessageType.AGENT_STOP):
    pass