import random
import time
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.chains import ConversationChain
from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAIChat
from langchain.memory import ConversationBufferMemory
from langchain.schema import ChatMessage, AIMessage
import openai
import json
from typing import Generator, Optional, Tuple

from typing import Generator
import logging
from vocode import getenv

from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.utils.sse_client import SSEClient
from vocode.streaming.agent.utils import stream_llm_response


class ChatGPTAgent(BaseAgent):
    def __init__(
        self,
        agent_config: ChatGPTAgentConfig,
        logger: logging.Logger = None,
        openai_api_key: Optional[str] = None,
    ):
        super().__init__(agent_config)
        openai.api_key = openai_api_key or getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment or passed in")
        self.agent_config = agent_config
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(agent_config.prompt_preamble),
                MessagesPlaceholder(variable_name="history"),
                HumanMessagePromptTemplate.from_template("{input}"),
            ]
        )
        self.memory = ConversationBufferMemory(return_messages=True)
        if agent_config.initial_message:
            if (
                agent_config.generate_responses
            ):  # we use ChatMessages for memory when we generate responses
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

    def respond(
        self,
        human_input,
        is_interrupt: bool = False,
        conversation_id: Optional[str] = None,
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
            text = self.conversation.predict(input=human_input)
        self.logger.debug(f"LLM response: {text}")
        return text, False

    def generate_response(
        self,
        human_input,
        is_interrupt: bool = False,
        conversation_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
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
        messages = SSEClient(
            "POST",
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {getenv('OPENAI_API_KEY')}",
            },
            json={
                "model": self.agent_config.model_name,
                "messages": [
                    prompt_message.dict(include={"content": True, "role": True})
                    for prompt_message in prompt_messages
                ],
                "max_tokens": 256,
                "temperature": 1.0,
                "stream": True,
            },
        )
        bot_memory_message = ChatMessage(role="assistant", content="")
        self.memory.chat_memory.messages.append(bot_memory_message)
        for message in stream_llm_response(
            map(lambda event: json.loads(event.data), messages),
            get_text=lambda choice: choice.get("delta", {}).get("content"),
        ):
            bot_memory_message.content = f"{bot_memory_message.content} {message}"
            yield message

    def update_last_bot_message_on_cut_off(self, message: str):
        for memory_message in self.memory.chat_memory.messages[::-1]:
            if (
                isinstance(memory_message, ChatMessage)
                and memory_message.role == "assistant"
            ) or isinstance(memory_message, AIMessage):
                memory_message.content = message
                return


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    agent = ChatGPTAgent(
        ChatGPTAgentConfig(
            prompt_preamble="The assistant is having a pleasant conversation about life. If the user hasn't completed their thought, the assistant responds with 'PASS'",
        )
    )
    while True:
        response = agent.respond(input("Human: "))[0]
        print(f"AI: {response}")
        # for response in agent.generate_response(input("Human: ")):
        #     print(f"AI: {response}")
