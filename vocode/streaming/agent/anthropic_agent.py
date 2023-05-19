from typing import AsyncGenerator, Optional
import logging

import anthropic

from langchain import ConversationChain
from langchain import ConversationChain
from langchain.schema import ChatMessage, AIMessage, HumanMessage
from langchain.chat_models import ChatAnthropic
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
)

from vocode import getenv
from vocode.streaming.agent.base_agent import (
    AgentResponse,
    AgentResponseMessage,
    GeneratorAgentResponse,
    OneShotAgentResponse,
    TextAgentResponseMessage
)
from vocode.streaming.agent.chat_agent import ChatAgent
from vocode.streaming.agent.utils import get_sentence_from_buffer
from vocode.streaming.models.agent import ChatAnthropicAgentConfig
from vocode.streaming.transcriber.base_transcriber import Transcription

SENTENCE_ENDINGS = [".", "!", "?"]


class ChatAnthropicAgent(ChatAgent[ChatAnthropicAgentConfig]):
    def __init__(
        self,
        agent_config: ChatAnthropicAgentConfig,
        logger: Optional[logging.Logger] = None,
        anthropic_api_key: Optional[str] = None,
    ):
        super().__init__(agent_config=agent_config, logger=logger)

        anthropic_api_key = anthropic_api_key or getenv("ANTHROPIC_API_KEY")
        if not anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set in environment or passed in"
            )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="history"),
                HumanMessagePromptTemplate.from_template("{input}"),
            ]
        )
        if agent_config.initial_message:
            raise NotImplementedError("initial_message not implemented for Anthropic")

        self.llm = ChatAnthropic(
            model=agent_config.model_name,
            anthropic_api_key=anthropic_api_key,
        )

        # streaming not well supported by langchain, so we will connect directly
        self.anthropic_client = (
            anthropic.Client(api_key=anthropic_api_key)
            if agent_config.generate_responses
            else None
        )

        self.conversation = ConversationChain(
            memory=self.memory, prompt=self.prompt, llm=self.llm
        )

    async def did_add_transcript_to_input_queue(self, transcription: Transcription):
        await super().did_add_transcript_to_input_queue(transcription)

        agent_response: AgentResponse

        if self.agent_config.generate_responses:
            generator = self._create_generator_response(transcription)
            agent_response = GeneratorAgentResponse(generator=generator)
        else:
            text = await self.conversation.apredict(input=transcription.message)
            self.logger.debug(f"LLM response: {text}")
            message = TextAgentResponseMessage(text=text)
            agent_response = OneShotAgentResponse(message=message)

        await self.add_agent_response_to_output_queue(response=agent_response)

    async def _create_generator_response(self, transcription: Transcription) -> AsyncGenerator[AgentResponseMessage, None]:
        self.memory.chat_memory.messages.append(HumanMessage(content=transcription.message))

        streamed_response = await self.anthropic_client.acompletion_stream(
            prompt=self.llm._convert_messages_to_prompt(
                self.memory.chat_memory.messages
            ),
            max_tokens_to_sample=self.agent_config.max_tokens_to_sample,
            model=self.agent_config.model_name,
        )

        bot_memory_message = AIMessage(content="")
        self.memory.chat_memory.messages.append(bot_memory_message)

        buffer = ""
        async for message in streamed_response:
            completion = message["completion"]
            delta = completion[len(bot_memory_message.content + buffer) :]
            buffer += delta

            sentence, remainder = get_sentence_from_buffer(buffer)

            if sentence:
                bot_memory_message.content = bot_memory_message.content + sentence
                buffer = remainder
                yield TextAgentResponseMessage(text=sentence)
            continue

    def _find_last_punctuation(self, buffer: str):
        indices = [buffer.rfind(ending) for ending in SENTENCE_ENDINGS]
        return indices and max(indices)

    def _get_sentence_from_buffer(self, buffer: str):
        last_punctuation = self._find_last_punctuation(buffer)
        if last_punctuation:
            return buffer[: last_punctuation + 1], buffer[last_punctuation + 1 :]
        else:
            return None, None

    def _update_last_bot_message_on_cut_off(self, message: str):
        for memory_message in self.memory.chat_memory.messages[::-1]:
            if (
                isinstance(memory_message, ChatMessage)
                and memory_message.role == "assistant"
            ) or isinstance(memory_message, AIMessage):
                memory_message.content = message
                return
