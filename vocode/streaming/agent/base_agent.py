from enum import Enum
import asyncio
import logging
import random
from typing import AsyncGenerator, Optional, Union
from vocode.streaming.models.agent import (
    AgentConfig,
    ChatGPTAgentConfig,
    LLMAgentConfig,
)
from vocode.streaming.models.model import TypedModel
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils.worker import AsyncWorker, InterruptibleEvent, QueueType, ThreadAsyncWorker

# --- Agent Response Messages ---


class AgentMessageResponseType(str, Enum):
    BASE = "base_agent_message_response"
    TEXT = "text_agent_message_response"
    TEXT_AND_STOP = "text_and_stop_agent_message_response"
    STOP = "stop_agent_message_response"


class AgentResponseMessage(TypedModel, type=AgentMessageResponseType.BASE):
    conversation_id: Optional[str] = None


class TextAgentResponseMessage(TypedModel, type=AgentMessageResponseType.TEXT):
    text: str


class TextAndStopAgentResponseMessage(TypedModel, type=AgentMessageResponseType.TEXT_AND_STOP):
    text: str


class StopAgentResponseMessage(TypedModel, type=AgentMessageResponseType.STOP):
    pass

# --- Agent Responses ---


class AgentResponse:
    pass


class OneShotAgentResponse(AgentResponse):
    message: AgentResponseMessage

    def __init__(self, message: AgentResponseMessage):
        self.message = message


class GeneratorAgentResponse(AgentResponse):
    generator: AsyncGenerator[AgentResponseMessage, None]

    def __init__(self, generator: AsyncGenerator[AgentResponseMessage, None]):
        self.generator = generator

# --- Abstract Agent ---


class AbstractAgent:
    def __init__(
        self, agent_config: AgentConfig, logger: Optional[logging.Logger] = None
    ):
        self.agent_config = agent_config
        self.logger = logger or logging.getLogger(__name__)

    def get_agent_config(self) -> AgentConfig:
        return self.agent_config

    async def add_transcript_to_input_queue(self, transcription: Transcription):
        pass

    async def did_add_transcript_to_input_queue(self, transcription: Transcription):
        pass

    def update_last_bot_message_on_cut_off(self, message: str):
        """Updates the last bot message in the conversation history when the human cuts off the bot's response."""
        pass

    def get_cut_off_response(self) -> Optional[str]:
        assert isinstance(self.agent_config, LLMAgentConfig) or isinstance(
            self.agent_config, ChatGPTAgentConfig
        )
        on_cut_off_messages = self.agent_config.cut_off_response.messages
        if on_cut_off_messages:
            return random.choice(on_cut_off_messages).text

# --- Base Async Agent ---


class BaseAsyncAgent(AsyncWorker, AbstractAgent):
    def __init__(
        self, agent_config: AgentConfig, logger: Optional[logging.Logger] = None
    ):
        self.input_queue: QueueType[InterruptibleEvent[Transcription]] = asyncio.Queue()
        self.output_queue: QueueType[InterruptibleEvent[AgentResponse]] = asyncio.Queue()
        self.agent_config = agent_config
        self.logger = logger or logging.getLogger(__name__)
        AsyncWorker.__init__(self, self.input_queue, self.output_queue)
        AbstractAgent.__init__(self, agent_config, logger)

    async def _run_loop(self) -> None:
        pass

    async def add_transcript_to_input_queue(self, transcription: Transcription) -> None:
        self.send_nonblocking(transcription)
        await self.did_add_transcript_to_input_queue(transcription)

    def add_agent_response_to_output_queue(self, response: AgentResponse) -> None:
        event = InterruptibleEvent(
            is_interruptible=self.agent_config.allow_agent_to_be_cut_off,
            payload=response,
        )
        self.output_queue.put_nowait(event)

    def terminate(self) -> None:
        AsyncWorker.terminate(self)

# --- Base Thread Async Agent ---


class BaseThreadAsyncAgent(ThreadAsyncWorker, AbstractAgent):
    def __init__(
        self, agent_config: AgentConfig, logger: Optional[logging.Logger] = None
    ):
        self.input_queue: QueueType[Transcription] = asyncio.Queue()
        self.output_queue: QueueType[AgentResponse] = asyncio.Queue()
        self.agent_config = agent_config
        self.logger = logger or logging.getLogger(__name__)
        ThreadAsyncWorker.__init__(self, self.input_queue, self.output_queue)
        AbstractAgent.__init__(self, agent_config, logger)

    async def _run_loop(self) -> None:
        pass

    async def add_transcript_to_input_queue(self, transcription: Transcription) -> None:
        self.send_nonblocking(transcription)
        await self.did_add_transcript_to_input_queue(transcription)

    def add_agent_response_to_output_queue(self, response: AgentResponse) -> None:
        event = InterruptibleEvent(
            is_interruptible=self.agent_config.allow_agent_to_be_cut_off,
            payload=response,
        )
        self.output_queue.put_nowait(event)

    def terminate(self) -> None:
        ThreadAsyncWorker.terminate(self)


BaseAgent = Union[BaseAsyncAgent, BaseThreadAsyncAgent]
