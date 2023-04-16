from typing import List, Optional, Union
from enum import Enum

from pydantic import validator

from vocode.streaming.models.message import BaseMessage
from .model import TypedModel, BaseModel

FILLER_AUDIO_DEFAULT_SILENCE_THRESHOLD_SECONDS = 0.5
LLM_AGENT_DEFAULT_TEMPERATURE = 1.0
LLM_AGENT_DEFAULT_MAX_TOKENS = 256
LLM_AGENT_DEFAULT_MODEL_NAME = "text-curie-001"
CHAT_GPT_AGENT_DEFAULT_MODEL_NAME = "gpt-3.5-turbo"


class AgentType(str, Enum):
    BASE = "agent_base"
    LLM = "agent_llm"
    CHAT_GPT_ALPHA = "agent_chat_gpt_alpha"
    CHAT_GPT = "agent_chat_gpt"
    ECHO = "agent_echo"
    INFORMATION_RETRIEVAL = "agent_information_retrieval"
    RESTFUL_USER_IMPLEMENTED = "agent_restful_user_implemented"
    WEBSOCKET_USER_IMPLEMENTED = "agent_websocket_user_implemented"


class FillerAudioConfig(BaseModel):
    silence_threshold_seconds: float = FILLER_AUDIO_DEFAULT_SILENCE_THRESHOLD_SECONDS
    use_phrases: bool = True
    use_typing_noise: bool = False

    @validator("use_typing_noise")
    def typing_noise_excludes_phrases(cls, v, values):
        if v and values.get("use_phrases"):
            values["use_phrases"] = False
        if not v and not values.get("use_phrases"):
            raise ValueError("must use either typing noise or phrases for filler audio")
        return v


class WebhookConfig(BaseModel):
    url: str


class AgentConfig(TypedModel, type=AgentType.BASE.value):
    initial_message: Optional[BaseMessage] = None
    generate_responses: bool = True
    allowed_idle_time_seconds: Optional[float] = None
    allow_agent_to_be_cut_off: bool = True
    end_conversation_on_goodbye: bool = False
    send_filler_audio: Union[bool, FillerAudioConfig] = False
    webhook_config: Optional[WebhookConfig] = None
    track_bot_sentiment: bool = False


class CutOffResponse(BaseModel):
    messages: List[BaseMessage] = [BaseMessage(text="Sorry?")]


class LLMAgentConfig(AgentConfig, type=AgentType.LLM.value):
    prompt_preamble: str
    expected_first_prompt: Optional[str] = None
    model_name: str = LLM_AGENT_DEFAULT_MODEL_NAME
    temperature: float = LLM_AGENT_DEFAULT_TEMPERATURE
    max_tokens: int = LLM_AGENT_DEFAULT_MAX_TOKENS
    cut_off_response: Optional[CutOffResponse] = None


class ChatGPTAgentConfig(AgentConfig, type=AgentType.CHAT_GPT.value):
    prompt_preamble: str
    expected_first_prompt: Optional[str] = None
    generate_responses: bool = False
    model_name: str = CHAT_GPT_AGENT_DEFAULT_MODEL_NAME
    temperature: float = LLM_AGENT_DEFAULT_TEMPERATURE
    max_tokens: int = LLM_AGENT_DEFAULT_MAX_TOKENS
    cut_off_response: Optional[CutOffResponse] = None


class InformationRetrievalAgentConfig(
    AgentConfig, type=AgentType.INFORMATION_RETRIEVAL.value
):
    recipient_descriptor: str
    caller_descriptor: str
    goal_description: str
    fields: List[str]
    # TODO: add fields for IVR, voicemail


class EchoAgentConfig(AgentConfig, type=AgentType.ECHO.value):
    pass


class RESTfulUserImplementedAgentConfig(
    AgentConfig, type=AgentType.RESTFUL_USER_IMPLEMENTED.value
):
    class EndpointConfig(BaseModel):
        url: str
        method: str = "POST"

    respond: EndpointConfig
    generate_responses: bool = False
    # generate_response: Optional[EndpointConfig]
    # update_last_bot_message_on_cut_off: Optional[EndpointConfig]


class RESTfulAgentInput(BaseModel):
    conversation_id: str
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


class WebSocketUserImplementedAgentConfig(
    AgentConfig, type=AgentType.WEBSOCKET_USER_IMPLEMENTED.value
):
    class RouteConfig(BaseModel):
        url: str

    respond: RouteConfig
    generate_responses: bool = False
    # generate_response: Optional[RouteConfig]
    # send_message_on_cut_off: bool = False


class WebSocketAgentMessageType(str, Enum):
    BASE = "websocket_agent_base"
    START = "websocket_agent_start"
    TEXT = "websocket_agent_text"
    TEXT_END = "websocket_agent_text_end"
    READY = "websocket_agent_ready"
    STOP = "websocket_agent_stop"


class WebSocketAgentMessage(TypedModel, type=WebSocketAgentMessageType.BASE):
    conversation_id: Optional[str] = None


class WebSocketAgentTextMessage(
    WebSocketAgentMessage, type=WebSocketAgentMessageType.TEXT
):
    class Payload(BaseModel):
        text: str

    data: Payload

    @classmethod
    def from_text(cls, text: str, conversation_id: Optional[str] = None):
        return cls(data=cls.Payload(text=text), conversation_id=conversation_id)


class WebSocketAgentStartMessage(
    WebSocketAgentMessage, type=WebSocketAgentMessageType.START
):
    pass


class WebSocketAgentReadyMessage(
    WebSocketAgentMessage, type=WebSocketAgentMessageType.READY
):
    pass


class WebSocketAgentStopMessage(
    WebSocketAgentMessage, type=WebSocketAgentMessageType.STOP
):
    pass


class WebSocketAgentTextEndMessage(
    WebSocketAgentMessage, type=WebSocketAgentMessageType.TEXT_END
):
    pass
