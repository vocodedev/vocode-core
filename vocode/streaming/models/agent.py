from enum import Enum
from typing import List, Optional, Union, Any

from jinja2 import Template
from langchain.prompts import PromptTemplate
from pydantic import validator

from vocode.streaming.models.actions import ActionConfig
from vocode.streaming.models.message import BaseMessage
from .model import TypedModel, BaseModel
from .vector_db import VectorDBConfig

CHAT_GPT_AGENT_LAST_USER_MESSAGE_COUNT = 5

FILLER_AUDIO_DEFAULT_SILENCE_THRESHOLD_SECONDS = 0.5
LLM_AGENT_DEFAULT_TEMPERATURE = 1.0
LLM_AGENT_DEFAULT_MAX_TOKENS = 256
LLM_AGENT_DEFAULT_MODEL_NAME = "text-curie-001"
CHAT_GPT_AGENT_DEFAULT_MODEL_NAME = "gpt-3.5-turbo-0613"
CHAT_GPT_INITIAL_MESSAGE_MODEL_NAME = "gpt-3.5-turbo"
ACTION_AGENT_DEFAULT_MODEL_NAME = "gpt-3.5-turbo-0613"
CHAT_ANTHROPIC_DEFAULT_MODEL_NAME = "claude-v1"
CHAT_VERTEX_AI_DEFAULT_MODEL_NAME = "chat-bison@001"
AZURE_OPENAI_DEFAULT_API_TYPE = "azure"
AZURE_OPENAI_DEFAULT_API_VERSION = "2023-03-15-preview"
AZURE_OPENAI_DEFAULT_ENGINE = "gpt-35-turbo"


class AgentType(str, Enum):
    BASE = "agent_base"
    LLM = "agent_llm"
    CHAT_GPT_ALPHA = "agent_chat_gpt_alpha"
    CHAT_GPT = "agent_chat_gpt"
    CHAT_GPT_CUSTOM = "agent_chat_gpt_custom"
    CHAT_ANTHROPIC = "agent_chat_anthropic"
    CHAT_VERTEX_AI = "agent_chat_vertex_ai"
    ECHO = "agent_echo"
    GPT4ALL = "agent_gpt4all"
    LLAMACPP = "agent_llamacpp"
    INFORMATION_RETRIEVAL = "agent_information_retrieval"
    RESTFUL_USER_IMPLEMENTED = "agent_restful_user_implemented"
    WEBSOCKET_USER_IMPLEMENTED = "agent_websocket_user_implemented"
    ACTION = "agent_action"


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


class AzureOpenAIConfig(BaseModel):
    api_type: str = AZURE_OPENAI_DEFAULT_API_TYPE
    api_version: Optional[str] = AZURE_OPENAI_DEFAULT_API_VERSION
    engine: str = AZURE_OPENAI_DEFAULT_ENGINE


class AgentConfig(TypedModel, type=AgentType.BASE.value):
    initial_message: Optional[BaseMessage] = None
    generate_responses: bool = True
    allowed_idle_time_seconds: Optional[float] = None
    allow_agent_to_be_cut_off: bool = True
    end_conversation_on_goodbye: bool = False
    send_filler_audio: Union[bool, FillerAudioConfig] = False
    webhook_config: Optional[WebhookConfig] = None
    track_bot_sentiment: bool = False
    actions: Optional[List[ActionConfig]] = None

    initial_audio_path: Optional[str] = None  # path to audio file.
    # Filler picker specials
    language: Optional[str] = None  # Language of the fillers to be used (determines the folder)
    prompt_template: Optional[
        dict] = None  # Prompt template to be used for filler generation (SAY part mostly). Passed as dict.


class CutOffResponse(BaseModel):
    messages: List[BaseMessage] = [BaseMessage(text="Sorry?")]


class LLMAgentConfig(AgentConfig, type=AgentType.LLM.value):
    prompt_preamble: str
    expected_first_prompt: Optional[str] = None
    model_name: str = LLM_AGENT_DEFAULT_MODEL_NAME
    temperature: float = LLM_AGENT_DEFAULT_TEMPERATURE
    max_tokens: int = LLM_AGENT_DEFAULT_MAX_TOKENS
    cut_off_response: Optional[CutOffResponse] = None


class ChatGPTFunctionsConfig(BaseModel):
    temperature: float = 0.2
    api_version: Optional[str] = None
    n: int = 3


class ChatGPTAgentConfig(AgentConfig, type=AgentType.CHAT_GPT.value):
    prompt_preamble: Union[Template, str]
    call_script: Optional[Any] = None
    dialog_state: Optional[Any] = None  # TODO: figure out how to do better because call_script point to this too.
    # right now it is used for twillio integration.

    expected_first_prompt: Optional[str] = None
    model_name: str = CHAT_GPT_AGENT_DEFAULT_MODEL_NAME
    max_tokens: int = 500
    max_total_tokens: int = 4096  # limit for 4k model.
    cut_off_response: Optional[CutOffResponse] = None
    azure_params: Optional[AzureOpenAIConfig] = None
    chat_gpt_functions_config: ChatGPTFunctionsConfig = ChatGPTFunctionsConfig()
    vector_db_config: Optional[VectorDBConfig] = None
    presence_penalty: float = 0.3
    frequency_penalty: float = 0.3
    temperature: float = 0.2
    top_p: float = 0.95
    last_messages_cnt: int = CHAT_GPT_AGENT_LAST_USER_MESSAGE_COUNT

    max_chars_check: int = 600

    class Config:
        arbitrary_types_allowed = True


class ChatGPTAgentConfigOLD(AgentConfig, type=AgentType.CHAT_GPT_CUSTOM.value):
    prompt_preamble: str
    expected_first_prompt: Optional[str] = None
    model_name: str = CHAT_GPT_AGENT_DEFAULT_MODEL_NAME
    initial_message_model_name: str = CHAT_GPT_AGENT_DEFAULT_MODEL_NAME
    temperature: float = LLM_AGENT_DEFAULT_TEMPERATURE
    max_tokens: int = LLM_AGENT_DEFAULT_MAX_TOKENS
    cut_off_response: Optional[CutOffResponse] = None
    azure_params: Optional[AzureOpenAIConfig] = None
    vector_db_config: Optional[VectorDBConfig] = None
    initial_audio_path: Optional[str] = None
    seed: Optional[int] = None
    timeout_seconds: float = 5  # timeout to get ENTIRE sentence from GPT. SLOW
    timeout_generator_seconds: float = 3  # timeout to get generator from GPT. FAST
    max_retries: int = 4
    retry_time_increment_seconds: float = 1


class ChatAnthropicAgentConfig(AgentConfig, type=AgentType.CHAT_ANTHROPIC.value):
    prompt_preamble: str
    model_name: str = CHAT_ANTHROPIC_DEFAULT_MODEL_NAME
    max_tokens_to_sample: int = 200


class ChatVertexAIAgentConfig(AgentConfig, type=AgentType.CHAT_VERTEX_AI.value):
    prompt_preamble: str
    model_name: str = CHAT_VERTEX_AI_DEFAULT_MODEL_NAME
    generate_responses: bool = False  # Google Vertex AI doesn't support streaming


class LlamacppAgentConfig(AgentConfig, type=AgentType.LLAMACPP.value):
    prompt_preamble: str
    llamacpp_kwargs: dict = {}
    prompt_template: Optional[Union[PromptTemplate, str]] = None


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


class GPT4AllAgentConfig(AgentConfig, type=AgentType.GPT4ALL.value):
    prompt_preamble: str
    model_path: str
    generate_responses: bool = False


class RESTfulUserImplementedAgentConfig(
    AgentConfig, type=AgentType.RESTFUL_USER_IMPLEMENTED.value
):
    class EndpointConfig(BaseModel):
        url: str
        method: str = "POST"

    respond: EndpointConfig
    generate_responses: bool = False
    # generate_response: Optional[EndpointConfig]


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
