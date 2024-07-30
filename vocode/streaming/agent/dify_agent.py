import json
import os
import random
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, TypeVar, Union

import sentry_sdk
from loguru import logger
from openai import DEFAULT_MAX_RETRIES as OPENAI_DEFAULT_MAX_RETRIES
from openai import AsyncAzureOpenAI, AsyncOpenAI, NotFoundError, RateLimitError

from vocode import sentry_span_tags
from vocode.streaming.action.abstract_factory import AbstractActionFactory
from vocode.streaming.action.default_factory import DefaultActionFactory
from vocode.streaming.agent.base_agent import GeneratedResponse, RespondAgent, StreamedResponse
from vocode.streaming.agent.openai_utils import (
    format_openai_chat_messages_from_transcript,
    openai_get_tokens,
    vector_db_result_to_openai_chat_message,
)
from vocode.streaming.agent.streaming_utils import collate_response_async, stream_response_async
from vocode.streaming.models.actions import FunctionCallActionTrigger
from vocode.streaming.models.agent import ChatGPTAgentConfig, DifyAgentConfig
from vocode.streaming.models.events import Sender
from vocode.streaming.models.message import BaseMessage, BotBackchannel, LLMToken
from vocode.streaming.models.transcript import Message
from vocode.streaming.utils.dify_client import ChatClient
from vocode.streaming.vector_db.factory import VectorDBFactory
from vocode.utils.sentry_utils import CustomSentrySpans, sentry_create_span

DifyAgentConfigType = TypeVar("DifyAgentConfigType", bound=DifyAgentConfig)


def instantiate_dify_client(agent_config: DifyAgentConfig, model_fallback: bool = False):
        return ChatClient(
            api_key=agent_config.api_key or os.environ.get("DIFY_API_KEY"),
            base_url=agent_config.base_url_override or "https://api.dify.com/v1",
            max_retries=agent_config.max_retries or 3,
        )

class DifyAgent(RespondAgent[DifyAgentConfigType]):
    dify_client: ChatClient

    def __init__(
        self,
        agent_config: DifyAgentConfigType,
        action_factory: AbstractActionFactory = DefaultActionFactory(),
        vector_db_factory=VectorDBFactory(),
        **kwargs,
    ):
        super().__init__(
            agent_config=agent_config,
            action_factory=action_factory,
            **kwargs,
        )
        self.dify_client = instantiate_dify_client(
            agent_config, model_fallback=agent_config.llm_fallback is not None
        )

        if not self.dify_client.api_key:
            raise ValueError("DIFY_API_KEY must be set in environment or passed in")

        if self.agent_config.vector_db_config:
            self.vector_db = vector_db_factory.create_vector_db(self.agent_config.vector_db_config)

    def get_functions(self):
        assert self.agent_config.actions
        if not self.action_factory:
            return None
        return [
            self.action_factory.create_action(action_config).get_openai_function()
            for action_config in self.agent_config.actions
            if isinstance(action_config.action_trigger, FunctionCallActionTrigger)
        ]

    def get_chat_parameters(self, messages: Optional[List] = None, use_functions: bool = True):
        assert self.transcript is not None
        is_azure = self._is_azure_model()

        messages = messages or format_openai_chat_messages_from_transcript(
            self.transcript,
            self.get_model_name_for_tokenizer(),
            self.functions,
            self.agent_config.prompt_preamble,
        )

        parameters: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": self.agent_config.max_tokens,
            "temperature": self.agent_config.temperature,
        }

        if is_azure:
            assert self.agent_config.azure_params is not None
            parameters["model"] = self.agent_config.azure_params.deployment_name
        else:
            parameters["model"] = self.agent_config.model_name

        if use_functions and self.functions:
            parameters["functions"] = self.functions

        return parameters

    def _is_azure_model(self) -> bool:
        return self.agent_config.azure_params is not None

    def get_model_name_for_tokenizer(self):
        if not self.agent_config.azure_params:
            return self.agent_config.model_name
        else:
            return self.agent_config.azure_params.openai_model_name

    def apply_model_fallback(self, chat_parameters: Dict[str, Any]):
        if self.agent_config.llm_fallback is None:
            return
        if self.agent_config.llm_fallback.provider == "openai":
            self.agent_config.model_name = self.agent_config.llm_fallback.model_name
            if isinstance(self.dify_client, AsyncAzureOpenAI):
                self.agent_config.azure_params = None
        else:
            if self.agent_config.azure_params:
                self.agent_config.azure_params.deployment_name = (
                    self.agent_config.llm_fallback.model_name
                )
                if isinstance(self.dify_client, AsyncOpenAI):
                    # TODO: handle OpenAI fallback to Azure
                    pass

        self.dify_client = instantiate_dify_client(self.agent_config, model_fallback=False)
        chat_parameters["model"] = self.agent_config.llm_fallback.model_name

    async def _create_openai_stream_with_fallback(
        self, chat_parameters: Dict[str, Any]
    ) -> AsyncGenerator:
        try:
            stream = await self.dify_client.chat.completions.create(**chat_parameters)
        except (NotFoundError, RateLimitError) as e:
            logger.error(
                f"{'Model not found' if isinstance(e, NotFoundError) else 'Rate limit error'} for model_name: {chat_parameters.get('model')}. Applying fallback.",
                exc_info=True,
            )
            self.apply_model_fallback(chat_parameters)
            stream = await self.dify_client.chat.completions.create(**chat_parameters)
        return stream

    async def _create_openai_stream(self, chat_parameters: Dict[str, Any]) -> AsyncGenerator:
        if self.agent_config.llm_fallback is not None and self.dify_client.max_retries == 0:
            stream = await self._create_openai_stream_with_fallback(chat_parameters)
        else:
            stream = await self.dify_client.chat.completions.create(**chat_parameters)
        return stream

    def should_backchannel(self, human_input: str) -> bool:
        return (
            not self.is_first_response()
            and not human_input.strip().endswith("?")
            and random.random() < self.agent_config.backchannel_probability
        )

    def choose_backchannel(self) -> Optional[BotBackchannel]:
        backchannel = None
        if self.transcript is not None:
            last_bot_message: Optional[Message] = None
            for event_log in self.transcript.event_logs[::-1]:
                if isinstance(event_log, Message) and event_log.sender == Sender.BOT:
                    last_bot_message = event_log
                    break
            if last_bot_message and last_bot_message.text.strip().endswith("?"):
                return BotBackchannel(text=self.post_question_bot_backchannel_randomizer())
        return backchannel

    async def generate_response(
        self,
        human_input: str,
        conversation_id: str,
        is_interrupt: bool = False,
        bot_was_in_medias_res: bool = False,
    ) -> AsyncGenerator[GeneratedResponse, None]:
        assert self.transcript is not None

        user = str(uuid.uuid4())
        chat_parameters = self.get_chat_parameters()
        chat_messages: List = chat_parameters.get("messages", [])

        stream = chat_messages[0]

        complete_response = ''
        partial_response = ''

        async for chunk in stream:
            chunk_string = chunk.decode()
            json_data = json.loads(chunk_string.replace('data: ', '').strip())
            content = json_data.get('answer', '')
            event = json_data.get('event', '')

            if event == 'node_started':
                complete_response = ''
                partial_response = ''

            if event == 'message':
                complete_response += content
                partial_response += content

            if partial_response and event == 'node_finished':
                dify_reply = {
                    'partialResponse': partial_response
                }
        using_input_streaming_synthesizer = (
        self.conversation_state_manager.using_input_streaming_synthesizer()
    )
        ResponseClass = (
            StreamedResponse if using_input_streaming_synthesizer else GeneratedResponse
        )
        MessageType = LLMToken if using_input_streaming_synthesizer else BaseMessage
        if isinstance(partial_response, str):
            yield ResponseClass(
                message=MessageType(text=partial_response),
                is_interruptible=True,
            )
        else:
            yield ResponseClass(
                message=partial_response,
                is_interruptible=True,
            )

    async def terminate(self):
        if hasattr(self, "vector_db") and self.vector_db is not None:
            await self.vector_db.tear_down()
        return await super().terminate()
