import re
from typing import AsyncGenerator, Optional, Tuple

from langchain import OpenAI
from typing import Generator
import logging

import openai
from vocode import getenv

from vocode.streaming.agent.base_agent import BaseAgent, RespondAgent
from vocode.streaming.agent.utils import collate_response_async, openai_get_tokens
from vocode.streaming.models.agent import LLMAgentConfig


class LLMAgent(RespondAgent[LLMAgentConfig]):
    SENTENCE_ENDINGS = [".", "!", "?"]

    DEFAULT_PROMPT_TEMPLATE = "{history}\nHuman: {human_input}\nAI:"

    def __init__(
        self,
        agent_config: LLMAgentConfig,
        logger: Optional[logging.Logger] = None,
        sender="AI",
        recipient="Human",
        openai_api_key: Optional[str] = None,
    ):
        super().__init__(agent_config)
        self.prompt_template = (
            f"{agent_config.prompt_preamble}\n\n{self.DEFAULT_PROMPT_TEMPLATE}"
        )
        self.initial_bot_message = (
            agent_config.initial_message.text if agent_config.initial_message else None
        )
        self.logger = logger or logging.getLogger(__name__)
        self.sender = sender
        self.recipient = recipient
        self.memory = (
            [f"AI: {agent_config.initial_message.text}"]
            if agent_config.initial_message
            else []
        )
        openai_api_key = openai_api_key or getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        self.llm = OpenAI(  # type: ignore
            model_name=self.agent_config.model_name,
            temperature=self.agent_config.temperature,
            max_tokens=self.agent_config.max_tokens,
            openai_api_key=openai_api_key,
        )
        self.stop_tokens = [f"{recipient}:"]
        self.first_response = (
            self.llm(
                self.prompt_template.format(
                    history="", human_input=agent_config.expected_first_prompt
                ),
                stop=self.stop_tokens,
            ).strip()
            if agent_config.expected_first_prompt
            else None
        )
        self.is_first_response = True

    def create_prompt(self, human_input):
        history = "\n".join(self.memory[-5:])
        return self.prompt_template.format(history=history, human_input=human_input)

    def get_memory_entry(self, human_input, response):
        return f"{self.recipient}: {human_input}\n{self.sender}: {response}"

    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[str, bool]:
        if is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            self.memory.append(self.get_memory_entry(human_input, cut_off_response))
            return cut_off_response, False
        self.logger.debug("LLM responding to human input")
        if self.is_first_response and self.first_response:
            self.logger.debug("First response is cached")
            self.is_first_response = False
            response = self.first_response
        else:
            response = (
                (
                    await self.llm.agenerate(
                        [self.create_prompt(human_input)], stop=self.stop_tokens
                    )
                )
                .generations[0][0]
                .text
            )
            response = response.replace(f"{self.sender}:", "")
        self.memory.append(self.get_memory_entry(human_input, response))
        self.logger.debug(f"LLM response: {response}")
        return response, False

    async def _stream_sentences(self, prompt):
        stream = await openai.Completion.acreate(
            prompt=prompt,
            max_tokens=self.agent_config.max_tokens,
            temperature=self.agent_config.temperature,
            model=self.agent_config.model_name,
            stop=self.stop_tokens,
            stream=True,
        )
        async for sentence in collate_response_async(
            openai_get_tokens(gen=stream),
        ):
            yield sentence

    async def _agen_from_list(self, l):
        for item in l:
            yield item

    async def generate_response(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> AsyncGenerator[str, None]:
        self.logger.debug("LLM generating response to human input")
        if is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            self.memory.append(self.get_memory_entry(human_input, cut_off_response))
            yield cut_off_response
            return
        self.memory.append(self.get_memory_entry(human_input, ""))
        if self.is_first_response and self.first_response:
            self.logger.debug("First response is cached")
            self.is_first_response = False
            sentences = self._agen_from_list([self.first_response])
        else:
            self.logger.debug("Creating LLM prompt")
            prompt = self.create_prompt(human_input)
            self.logger.debug("Streaming LLM response")
            sentences = self._stream_sentences(prompt)
        response_buffer = ""
        async for sentence in sentences:
            sentence = sentence.replace(f"{self.sender}:", "")
            sentence = re.sub(r"^\s+(.*)", r" \1", sentence)
            response_buffer += sentence
            self.memory[-1] = self.get_memory_entry(human_input, response_buffer)
            yield sentence

    def update_last_bot_message_on_cut_off(self, message: str):
        last_message = self.memory[-1]
        new_last_message = (
            last_message.split("\n", 1)[0] + f"\n{self.sender}: {message}"
        )
        self.memory[-1] = new_last_message
