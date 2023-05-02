from typing import AsyncGenerator, Optional, Tuple
from langchain import ConversationChain

from langchain.memory import ConversationBufferMemory
from langchain.schema import ChatMessage, AIMessage, HumanMessage
from langchain.chat_models import ChatAnthropic
import logging
from vocode import getenv

from vocode.streaming.agent.base_agent import BaseAgent

from vocode.streaming.models.agent import ChatAnthropicAgentConfig


from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
)

SENTENCE_ENDINGS = [".", "!", "?"]


class ChatAnthropicAgent(BaseAgent):
    def __init__(
        self,
        agent_config: ChatAnthropicAgentConfig,
        logger: logging.Logger = None,
        anthropic_api_key: Optional[str] = None,
    ):
        super().__init__(agent_config)
        import anthropic

        anthropic_api_key = anthropic_api_key or getenv("ANTHROPIC_API_KEY")
        if not anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set in environment or passed in"
            )
        self.agent_config = agent_config
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="history"),
                HumanMessagePromptTemplate.from_template("{input}"),
            ]
        )
        self.memory = ConversationBufferMemory(return_messages=True)
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

    async def respond(
        self,
        human_input,
        is_interrupt: bool = False,
        conversation_id: Optional[str] = None,
    ) -> Tuple[str, bool]:
        text = await self.conversation.apredict(input=human_input)
        self.logger.debug(f"LLM response: {text}")
        return text, False

    async def generate_response(
        self,
        human_input,
        is_interrupt: bool = False,
        conversation_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        self.memory.chat_memory.messages.append(HumanMessage(content=human_input))

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

            sentence, remainder = self.get_sentence_from_buffer(buffer)

            if sentence:
                bot_memory_message.content = bot_memory_message.content + sentence
                buffer = remainder
                yield sentence
            continue

    def find_last_punctuation(self, buffer: str):
        indices = [buffer.rfind(ending) for ending in SENTENCE_ENDINGS]
        return indices and max(indices)

    def get_sentence_from_buffer(self, buffer: str):
        last_punctuation = self.find_last_punctuation(buffer)
        if last_punctuation:
            return buffer[: last_punctuation + 1], buffer[last_punctuation + 1 :]
        else:
            return None, None

    def update_last_bot_message_on_cut_off(self, message: str):
        for memory_message in self.memory.chat_memory.messages[::-1]:
            if (
                isinstance(memory_message, ChatMessage)
                and memory_message.role == "assistant"
            ) or isinstance(memory_message, AIMessage):
                memory_message.content = message
                return
