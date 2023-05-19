import re
from typing import AsyncGenerator, Optional

from langchain import OpenAI
import logging

import openai
from vocode import getenv

from vocode.streaming.agent.base_agent import AgentResponseMessage, BaseAsyncAgent, TextAgentResponseMessage
from vocode.streaming.agent.utils import stream_openai_response_async
from vocode.streaming.models.agent import LLMAgentConfig
from vocode.streaming.transcriber.base_transcriber import Transcription


class LLMAgent(BaseAsyncAgent[LLMAgentConfig]):
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

    async def did_add_transcript_to_input_queue(self, transcription: Transcription):
        await super().did_add_transcript_to_input_queue(transcription)
        if self.agent_config.generate_responses:
            pass
        else:
            pass

    async def _create_generator_response(self, transcription: Transcription) -> AsyncGenerator[AgentResponseMessage, None]:
        self.logger.debug("LLM generating response to human input")
        human_input = transcription.message
        if transcription.is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            self.memory.append(self.get_memory_entry(human_input, cut_off_response))
            yield TextAgentResponseMessage(text=cut_off_response)
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
            yield TextAgentResponseMessage(text=sentence)

    async def _generate_one_shot_response(self, transcription: Transcription) -> AgentResponseMessage:
        is_interrupt = transcription.is_interrupt
        human_input = transcription.message
        if is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            self.memory.append(self.get_memory_entry(human_input, cut_off_response))
            return TextAgentResponseMessage(text=cut_off_response)

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
        return TextAgentResponseMessage(text=response)

    async def _stream_sentences(self, prompt):
        stream = await openai.Completion.acreate(
            prompt=prompt,
            max_tokens=self.agent_config.max_tokens,
            temperature=self.agent_config.temperature,
            model=self.agent_config.model_name,
            stop=self.stop_tokens,
            stream=True,
        )
        async for sentence in stream_openai_response_async(
            stream,
            get_text=lambda choice: choice.get("text"),
        ):
            yield sentence

    async def _agen_from_list(self, l):
        for item in l:
            yield item

    def update_last_bot_message_on_cut_off(self, message: str):
        last_message = self.memory[-1]
        new_last_message = (
            last_message.split("\n", 1)[0] + f"\n{self.sender}: {message}"
        )
        self.memory[-1] = new_last_message
