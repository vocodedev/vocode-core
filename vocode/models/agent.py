from typing import Optional
from enum import Enum
from .model import TypedModel


class AgentType(str, Enum):
    BASE = "base"
    LLM = "llm"
    CHAT_GPT = "chat_gpt"
    ECHO = "echo"
    INFORMATION_RETRIEVAL = "information_retrieval"


class AgentConfig(TypedModel, type=AgentType.BASE):
    initial_message: Optional[str] = None


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
