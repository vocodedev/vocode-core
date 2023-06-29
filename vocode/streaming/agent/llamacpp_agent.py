from concurrent.futures import ThreadPoolExecutor
import re
import asyncio
import logging
from typing import AsyncGenerator, Optional, Tuple, Any
from langchain import ConversationChain
from vocode.streaming.agent.base_agent import RespondAgent
from vocode.streaming.models.agent import LlamacppAgentConfig
from langchain.callbacks.base import BaseCallbackHandler
from langchain.callbacks.manager import CallbackManager
from langchain.llms import LlamaCpp
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

ALPACA_TEMPLATE_WITH_HISTORY = """### Instruction:
Your previous conversation history:
{history}

Current instruction/message to respond to: {input}
### Response:"""


class FormatHistoryPromptTemplate(PromptTemplate):
    def format(self, **kwargs: Any) -> str:
        kwargs = self._merge_partial_and_user_variables(**kwargs)
        kwargs["history"] = get_buffer_string(kwargs["history"])
        return DEFAULT_FORMATTER_MAPPING[self.template_format](self.template, **kwargs)


class CallbackOutput(BaseModel):
    finish: bool = False
    response: Optional[LLMResult] = None
    token: Optional[str] = None


class CustomStreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self, output_queue: asyncio.Queue) -> None:
        super().__init__()
        self.output_queue = output_queue

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Run on new LLM token. Only available when streaming is enabled."""
        self.output_queue.put_nowait(CallbackOutput(token=token))

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run when LLM ends running."""
        self.output_queue.put_nowait(CallbackOutput(finish=True, response=response))


class LlamacppAgent(RespondAgent[LlamacppAgentConfig]):
    def __init__(
        self,
        agent_config: LlamacppAgentConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(agent_config=agent_config, logger=logger)

        if type(agent_config.prompt_template) is str:
            if agent_config.prompt_template == "alpaca":
                self.prompt = FormatHistoryPromptTemplate(
                    input_variables=["history", "input"],
                    template=ALPACA_TEMPLATE_WITH_HISTORY,
                )
            else:
                raise ValueError(
                    f"Unknown prompt template {agent_config.prompt_template}"
                )
        else:
            self.prompt = (
                agent_config.prompt_template
                or ChatPromptTemplate.from_messages(
                    [
                        MessagesPlaceholder(variable_name="history"),
                        HumanMessagePromptTemplate.from_template("{input}"),
                    ]
                )
            )

        self.callback_queue = asyncio.Queue()
        callback = CustomStreamingCallbackHandler(self.callback_queue)
        callback_manager = CallbackManager([callback])
        self.llm = LlamaCpp(
            callback_manager=callback_manager, **agent_config.llamacpp_kwargs
        )

        self.memory = ConversationBufferMemory(return_messages=True)
        self.memory.chat_memory.messages.append(
            SystemMessage(content=self.agent_config.prompt_preamble)
        )

        self.conversation = ConversationChain(
            memory=self.memory, prompt=self.prompt, llm=self.llm
        )
        # if agent_config.initial_message:
        #     raise NotImplementedError("initial_message not supported for Vertex AI")
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
        sentence_endings_pattern = "|".join(map(re.escape, [".", "!", "?", "\n"]))
        list_item_ending_pattern = r"\n"
        buffer = ""
        prev_ends_with_money = False
        while True:
            callback_output = await self.callback_queue.get()
            if callback_output.finish:
                break
            token = callback_output.token
            if not token:
                continue

            if prev_ends_with_money and token.startswith(" "):
                yield buffer.strip()
                buffer = ""

            buffer += token
            possible_list_item = bool(re.match(r"^\d+[ .]", buffer))
            ends_with_money = bool(re.findall(r"\$\d+.$", buffer))
            if re.findall(
                list_item_ending_pattern
                if possible_list_item
                else sentence_endings_pattern,
                token,
            ):
                if not ends_with_money:
                    to_return = buffer.strip()
                    if to_return:
                        yield to_return
                    buffer = ""
            prev_ends_with_money = ends_with_money
        to_return = buffer.strip()
        if to_return:
            yield to_return
