import logging

from typing import Any, Dict, List, Union
from typing import AsyncGenerator, Optional, Tuple

import openai

from vocode import getenv
from vocode.streaming.action.factory import ActionFactory
from vocode.streaming.agent.base_agent import RespondAgent
from vocode.streaming.agent.utils import (
    format_openai_chat_messages_from_transcript,
    collate_response_async,
    openai_get_tokens)
from vocode.streaming.models.actions import FunctionCall
from vocode.streaming.models.agent import LLAMA3AgentConfig
from vocode.streaming.models.transcript import Transcript


class LLAMA3Agent(RespondAgent[LLAMA3AgentConfig]):
    def __init__(
            self,
            agent_config: LLAMA3AgentConfig,
            action_factory: ActionFactory = ActionFactory(),
            logger: Optional[logging.Logger] = None,
            api_key: Optional[str] = None,
    ):
        super().__init__(
            agent_config=agent_config, action_factory=action_factory, logger=logger
        )

        openai.api_type = "open_ai"
        openai.api_base = agent_config.api_base
        openai.api_version = None
        openai.api_key = api_key or getenv("LLAMA3_API_KEY")
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        self.first_response = None
        self.is_first_response = True

    def get_functions(self):
        return None  # LLAMA3 does not support functions yet.

    def get_chat_parameters(
            self, messages: Optional[List] = None, use_functions: bool = False, ignore_assert: bool = False
    ):
        if not ignore_assert:
            assert self.transcript is not None
        messages = messages or format_openai_chat_messages_from_transcript(
            self.transcript, self.agent_config.prompt_preamble
        )

        parameters: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": self.agent_config.max_tokens,
            "temperature": self.agent_config.temperature,
        }

        parameters["model"] = self.agent_config.model_name

        if use_functions and self.functions:
            raise NotImplementedError("LLAMA3 does not support functions yet.")
            # parameters["functions"] = self.functions

        return parameters

    async def create_first_response(self, first_message_prompt: Optional[str] = None):
        system_prompt = first_message_prompt if first_message_prompt else self.agent_config.prompt_preamble
        messages = [{"role": "system", "content": system_prompt}]
        parameters = self.get_chat_parameters(messages)
        parameters["stream"] = True
        self.logger.info('Attempting to stream response for first message.')
        stream = await openai.ChatCompletion.acreate(**parameters)
        async for message in collate_response_async(
                openai_get_tokens(stream)
        ):
            yield message, True

    async def create_first_response_full(self, first_message_prompt: Optional[str] = None):
        system_prompt = first_message_prompt if first_message_prompt else self.agent_config.prompt_preamble
        messages = [{"role": "system", "content": system_prompt}]
        parameters = self.get_chat_parameters(messages, ignore_assert=True)
        parameters["stream"] = False
        self.logger.info('Attempting create response for the first message.')
        chat_completion = await openai.ChatCompletion.acreate(**parameters)
        return chat_completion.choices[0].message.content

    def attach_transcript(self, transcript: Transcript):
        self.transcript = transcript

    async def respond(
            self,
            human_input,
            conversation_id: str,
            is_interrupt: bool = False,
    ) -> Tuple[str, bool]:
        assert self.transcript is not None
        if is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            return cut_off_response, False
        self.logger.debug("LLM responding to human input")
        if self.is_first_response and self.first_response:
            self.logger.debug("First response is cached")
            self.is_first_response = False
            text = self.first_response
        else:
            chat_parameters = self.get_chat_parameters()
            chat_completion = await openai.ChatCompletion.acreate(**chat_parameters)
            text = chat_completion.choices[0].message.content
        self.logger.debug(f"LLM response: {text}")
        return text, False

    async def generate_response(
            self,
            human_input: str,
            conversation_id: str,
            is_interrupt: bool = False,
    ) -> AsyncGenerator[Tuple[Union[str, FunctionCall], bool], None]:

        assert self.transcript is not None

        chat_parameters = self.get_chat_parameters()
        chat_parameters["stream"] = True

        self.logger.info('Attempting to stream response.')
        stream = await openai.ChatCompletion.acreate(**chat_parameters)
        async for message in collate_response_async(
                openai_get_tokens(stream)
        ):
            yield message, True
