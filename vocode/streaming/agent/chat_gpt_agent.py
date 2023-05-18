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
from langchain.schema import ChatMessage, AIMessage
import openai
from typing import AsyncGenerator, Optional, Tuple

import logging

from vocode import getenv
from vocode.streaming.agent.chat_agent import ChatAgent
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.agent.utils import stream_openai_response_async


class ChatGPTAgent(ChatAgent[ChatGPTAgentConfig]):
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
        self.llm = ChatOpenAI(  # type: ignore
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

    async def respond(  # type: ignore
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[str, bool]:
        if is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            self.memory.chat_memory.add_user_message(human_input)
            self.memory.chat_memory.add_ai_message(cut_off_response)
            return cut_off_response, False
        self.logger.debug("LLM responding to human input")
        if self.is_first_response and self.first_response:
            self.logger.debug("First response is cached")
            self.is_first_response = False
            text = self.first_response
        else:
            text = await self.conversation.apredict(input=human_input)
        self.logger.debug(f"LLM response: {text}")
        return text, False

    async def generate_response(
        self,
        human_input: str,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> AsyncGenerator[str, None]:
        self.memory.chat_memory.messages.append(
            ChatMessage(role="user", content=human_input)
        )
        if is_interrupt and self.agent_config.cut_off_response:
            cut_off_response = self.get_cut_off_response()
            self.memory.chat_memory.messages.append(
                ChatMessage(role="assistant", content=cut_off_response)
            )
            yield cut_off_response
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
            yield message
