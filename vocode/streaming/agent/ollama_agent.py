from concurrent.futures import ThreadPoolExecutor
import asyncio
import logging
from typing import AsyncGenerator, Optional, Tuple, Any, Union
import typing
from langchain import ConversationChain
from vocode.streaming.agent.base_agent import RespondAgent
from vocode.streaming.models.agent import OllamaAgentConfig
from vocode.streaming.agent.utils import collate_response_async
from langchain.callbacks.base import BaseCallbackHandler
from langchain.callbacks.manager import CallbackManager
from langchain.llms import Ollama
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
)
from pydantic import BaseModel
from langchain.schema import LLMResult, SystemMessage, get_buffer_string
from langchain.memory import ConversationBufferMemory
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
    PromptTemplate,
)
from langchain.prompts.base import DEFAULT_FORMATTER_MAPPING

from vocode.streaming.agent.llamacpp_agent import (
    CustomStreamingCallbackHandler,
)  # temporary just to get things working


class OllamaAgent(RespondAgent[OllamaAgentConfig]):
    def __init__(
        self,
        agent_config: OllamaAgentConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(agent_config=agent_config, logger=logger)
        self.callback_queue: asyncio.Queue = asyncio.Queue()
        callback = CustomStreamingCallbackHandler(self.callback_queue)
        callback_manager = CallbackManager([callback])
        self.llm = Ollama(
            callback_manager=callback_manager, base_url=self.agent_config.ollama_server
        )
        self.prompt: Union[
            PromptTemplate, ChatPromptTemplate
        ] = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="history"),
                HumanMessagePromptTemplate.from_template("{input}"),
            ]
        )
        self.memory = ConversationBufferMemory(return_messages=True)
        self.memory.chat_memory.messages.append(
            SystemMessage(content=self.agent_config.prompt_preamble)
        )

        self.conversation = ConversationChain(
            memory=self.memory, prompt=self.prompt, llm=self.llm
        )
        self.thread_pool_executor = ThreadPoolExecutor(max_workers=1)

    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[str, bool]:
        text = await asyncio.get_event_loop().run_in_executor(
            self.thread_pool_executor,
            lambda input: self.conversation.predict(input=input),
            human_input,
        )

        self.logger.debug(f"LLM response: {text}")
        return text, False

    async def ollama_get_tokens(self):
        while True:
            callback_output = await self.callback_queue.get()
            if callback_output.finish:
                break
            yield callback_output.token

    async def generate_response(
        self,
        human_input: str,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> AsyncGenerator[str, None]:
        asyncio.get_event_loop().run_in_executor(
            self.thread_pool_executor,
            lambda input: self.conversation.predict(input=input),
            human_input,
        )

        async for message in collate_response_async(
            self.ollama_get_tokens(),
        ):
            yield str(message)
