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
        input_param_name: str = "human_input"
        output_jsonpath: str = "response"

    respond: EndpointConfig
    generate_response: Optional[EndpointConfig]
    update_last_bot_message_on_cut_off: Optional[EndpointConfig]
