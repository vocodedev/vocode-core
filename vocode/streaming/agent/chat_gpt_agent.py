import logging

from typing import Generator, Optional, Tuple

from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from langchain.chains import ConversationChain
from langchain.chat_models import ChatOpenAI
from langchain.schema import ChatMessage
import openai
from typing import AsyncGenerator, Optional, Tuple

import logging

from vocode import getenv
from vocode.streaming.agent.base_agent import AgentResponse, AgentResponseMessage, GeneratorAgentResponse, OneShotAgentResponse, TextAgentResponseMessage
from vocode.streaming.agent.chat_agent import ChatAsyncAgent
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.agent.utils import stream_openai_response_async
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils.worker import InterruptibleEvent


class ChatGPTAgent(ChatAsyncAgent):
    def __init__(
        self,
        agent_config: ChatGPTAgentConfig,
        logger: Optional[logging.Logger] = None,
        openai_api_key: Optional[str] = None,
    ):
        super().__init__(agent_config=agent_config, logger=logger)
        self.agent_config = agent_config
        openai.api_key = openai_api_key or getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        self.prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(agent_config.prompt_preamble),
                MessagesPlaceholder(variable_name="history"),
                HumanMessagePromptTemplate.from_template("{input}"),
            ]
        )
        if agent_config.initial_message:
            if agent_config.generate_responses:
                # we use ChatMessages for memory when we generate responses
                self.memory.chat_memory.messages.append(
                    ChatMessage(
                        content=agent_config.initial_message.text, role="assistant"
                    )
                )
            else:
                self.memory.chat_memory.add_ai_message(
                    agent_config.initial_message.text
                )
        self.llm = ChatOpenAI(
            model_name=self.agent_config.model_name,
            temperature=self.agent_config.temperature,
            max_tokens=self.agent_config.max_tokens,
            openai_api_key=openai.api_key,
        )
        self.conversation = ConversationChain(
            memory=self.memory, prompt=self.prompt, llm=self.llm
        )
        self.first_response = (
            self.create_first_response(agent_config.expected_first_prompt)
            if agent_config.expected_first_prompt
            else None
        )
        self.is_first_response = True

    def create_first_response(self, first_prompt):
        return self.conversation.predict(input=first_prompt)

    async def did_add_transcript_to_input_queue(self, transcription: Transcription):
        await super().did_add_transcript_to_input_queue(transcription)
        agent_response: AgentResponse

        if self.agent_config.generate_responses:
            generator = self._create_generator_response(transcription)
            agent_response = GeneratorAgentResponse(generator=generator)
        else:
            response_message = self._create_one_shot_response(transcription)
            agent_response = OneShotAgentResponse(message=response_message)
        self.add_agent_response_to_output_queue(response=agent_response)

    async def _create_generator_response(self, transcription: Transcription) -> AsyncGenerator[AgentResponseMessage, None]:
        self.memory.chat_memory.messages.append(
            ChatMessage(role="user", content=transcription.message)
        )
        if transcription.is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            self.memory.chat_memory.messages.append(
                ChatMessage(role="assistant", content=cut_off_response)
            )
            yield TextAgentResponseMessage(text=cut_off_response)
            return

        prompt_messages = [
            ChatMessage(role="system", content=self.agent_config.prompt_preamble)
        ] + self.memory.chat_memory.messages
        bot_memory_message = ChatMessage(role="assistant", content="")
        self.memory.chat_memory.messages.append(bot_memory_message)
        stream = await openai.ChatCompletion.acreate(
            model=self.agent_config.model_name,
            messages=[
                prompt_message.dict(include={"content": True, "role": True})
                for prompt_message in prompt_messages
            ],
            max_tokens=self.agent_config.max_tokens,
            temperature=self.agent_config.temperature,
            stream=True,
        )
        async for message in stream_openai_response_async(
            stream,
            get_text=lambda choice: choice.get("delta", {}).get("content"),
        ):
            bot_memory_message.content = f"{bot_memory_message.content} {message}"
            yield TextAgentResponseMessage(text=message)

    def _create_one_shot_response(self, transcription: Transcription) -> TextAgentResponseMessage:
        if transcription.is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            self.memory.chat_memory.add_user_message(transcription.message)
            self.memory.chat_memory.add_ai_message(cut_off_response)
            return TextAgentResponseMessage(text=cut_off_response)

        else:
            if self.is_first_response and self.first_response:
                self.logger.debug("First response is cached")
                self.is_first_response = False
                return TextAgentResponseMessage(text=self.first_response)
            else:
                text = self.conversation.predict(input=transcription.message)
                self.logger.debug(f"LLM response: {text}")
                return TextAgentResponseMessage(text=text)
