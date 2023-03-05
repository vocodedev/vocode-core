from typing import Optional
from enum import Enum
from .model import TypedModel, BaseModel


class AgentType(str, Enum):
    BASE = "agent_base"
    LLM = "agent_llm"
    CHAT_GPT_ALPHA = "agent_chat_gpt_alpha"
    CHAT_GPT = "agent_chat_gpt"
    ECHO = "agent_echo"
    INFORMATION_RETRIEVAL = "agent_information_retrieval"
    RESTFUL_USER_IMPLEMENTED = "agent_restful_user_implemented"
    WEBSOCKET_USER_IMPLEMENTED = "agent_websocket_user_implemented"


class AgentConfig(TypedModel, type=AgentType.BASE):
    initial_message: Optional[str] = None
    generate_responses: bool = True
    allowed_idle_time_seconds: Optional[float] = None

class LLMAgentConfig(AgentConfig, type=AgentType.LLM):
    prompt_preamble: str
    expected_first_prompt: Optional[str] = None

class ChatGPTAlphaAgentConfig(AgentConfig, type=AgentType.CHAT_GPT_ALPHA):
    prompt_preamble: str
    expected_first_prompt: Optional[str] = None

class ChatGPTAgentConfig(AgentConfig, type=AgentType.CHAT_GPT):
    prompt_preamble: str
    expected_first_prompt: Optional[str] = None
    generate_responses: bool = False

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

class RESTfulAgentOutputType(str, Enum):
    BASE = "restful_agent_base"
    TEXT = "restful_agent_text"
    END = "restful_agent_end"

class RESTfulAgentOutput(TypedModel, type=RESTfulAgentOutputType.BASE):
    pass

class RESTfulAgentText(RESTfulAgentOutput, type=RESTfulAgentOutputType.TEXT):
    response: str

class RESTfulAgentEnd(RESTfulAgentOutput, type=RESTfulAgentOutputType.END):
    pass

class WebSocketUserImplementedAgentConfig(AgentConfig, type=AgentType.WEBSOCKET_USER_IMPLEMENTED):
    class RouteConfig(BaseModel):
        url: str

    respond: RouteConfig
    generate_responses: bool = False
    # generate_response: Optional[RouteConfig]
    # send_message_on_cut_off: bool = False

class WebSocketAgentMessageType(str, Enum):
    BASE = 'websocket_agent_base'
    START = 'websocket_agent_start'
    TEXT = 'websocket_agent_text'
    READY = 'websocket_agent_ready'
    STOP = 'websocket_agent_stop'

class WebSocketAgentMessage(TypedModel, type=WebSocketAgentMessageType.BASE): pass

class WebSocketAgentTextMessage(WebSocketAgentMessage, type=WebSocketAgentMessageType.TEXT):
    class Payload(BaseModel):
        text: str

    data: Payload

    @classmethod
    def from_text(cls, text: str):
        return cls(data=cls.Payload(text=text))


class WebSocketAgentStartMessage(WebSocketAgentMessage, type=WebSocketAgentMessageType.START):
    pass

class WebSocketAgentReadyMessage(WebSocketAgentMessage, type=WebSocketAgentMessageType.READY):
    pass

class WebSocketAgentStopMessage(WebSocketAgentMessage, type=WebSocketAgentMessageType.STOP):
    pass
