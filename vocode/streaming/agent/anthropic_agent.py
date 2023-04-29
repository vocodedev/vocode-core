import logging
import anthropic

from typing import Generator, Optional, Tuple

from utils import get_sentence_from_buffer

from langchain import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import ChatMessage, AIMessage, HumanMessage
from langchain.chat_models import ChatAnthropic
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
)

from vocode import getenv
from vocode.streaming.agent.chat_agent import ChatAgent
from vocode.streaming.models.agent import ChatAnthropicAgentConfig

SENTENCE_ENDINGS = [".", "!", "?"]


class ChatAnthropicAgent(ChatAgent):
    def __init__(
        self,
        agent_config: ChatAnthropicAgentConfig,
        logger: logging.Logger = None,
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

    def respond(
        self,
        human_input,
        is_interrupt: bool = False,
        conversation_id: Optional[str] = None,
    ) -> Tuple[str, bool]:
        text = self.conversation.predict(input=human_input)
        self.logger.debug(f"LLM response: {text}")
        return text, False

    def generate_response(
        self,
        human_input,
        is_interrupt: bool = False,
        conversation_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        self.memory.chat_memory.messages.append(HumanMessage(content=human_input))

        streamed_response = self.anthropic_client.completion_stream(
            prompt=self.llm._convert_messages_to_prompt(
                self.memory.chat_memory.messages
            ),
            max_tokens_to_sample=self.agent_config.max_tokens_to_sample,
            model=self.agent_config.model_name,
        )

        bot_memory_message = AIMessage(content="")
        self.memory.chat_memory.messages.append(bot_memory_message)

        buffer = ""
        for message in streamed_response:
            completion = message["completion"]
            delta = completion[len(bot_memory_message.content + buffer) :]
            buffer += delta

            sentence, remainder = get_sentence_from_buffer(buffer)

            if sentence:
                bot_memory_message.content = bot_memory_message.content + sentence
                buffer = remainder
                yield sentence
            continue


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    agent = ChatAnthropicAgent(
        ChatAnthropicAgentConfig(),
    )

    while True:
        response = agent.generate_response(input("Human: "))
        for i in response:
            print(i)
