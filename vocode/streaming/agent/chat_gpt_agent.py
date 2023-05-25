import logging

from typing import Optional, Tuple

import openai
from typing import AsyncGenerator, Optional, Tuple

import logging

from vocode import getenv
from vocode.streaming.agent.base_agent import RespondAgent
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.agent.utils import (
    format_openai_chat_messages_from_transcript,
    stream_openai_response_async,
)
from vocode.streaming.utils.transcript import Transcript


class ChatGPTAgent(RespondAgent[ChatGPTAgentConfig]):
    def __init__(
        self,
        agent_config: ChatGPTAgentConfig,
        logger: Optional[logging.Logger] = None,
        openai_api_key: Optional[str] = None,
    ):
        super().__init__(agent_config=agent_config, logger=logger)
        openai.api_key = openai_api_key or getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        self.first_response = (
            self.create_first_response(agent_config.expected_first_prompt)
            if agent_config.expected_first_prompt
            else None
        )
        self.is_first_response = True

    def create_first_response(self, first_prompt):
        return openai.ChatCompletion.create(
            model=self.agent_config.model_name,
            messages=[
                (
                    [{"role": "system", "content": self.agent_config.prompt_preamble}]
                    if self.agent_config.prompt_preamble
                    else []
                )
                + [{"role": "user", "content": first_prompt}]
            ],
        )

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
            chat_completion = await openai.ChatCompletion.acreate(
                model=self.agent_config.model_name,
                messages=format_openai_chat_messages_from_transcript(
                    self.transcript, self.agent_config.prompt_preamble
                ),
                max_tokens=self.agent_config.max_tokens,
                temperature=self.agent_config.temperature,
            )
            text = chat_completion.choices[0].message.content
        self.logger.debug(f"LLM response: {text}")
        return text, False

    async def generate_response(
        self,
        human_input: str,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> AsyncGenerator[str, None]:
        if is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            yield cut_off_response
            return
        assert self.transcript is not None
        stream = await openai.ChatCompletion.acreate(
            model=self.agent_config.model_name,
            messages=format_openai_chat_messages_from_transcript(
                self.transcript, self.agent_config.prompt_preamble
            ),
            max_tokens=self.agent_config.max_tokens,
            temperature=self.agent_config.temperature,
            stream=True,
        )
        async for message in stream_openai_response_async(
            stream,
            get_text=lambda choice: choice.get("delta", {}).get("content"),
        ):
            yield message
