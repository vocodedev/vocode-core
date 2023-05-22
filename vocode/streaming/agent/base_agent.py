import asyncio
from enum import Enum
import logging
import random
from typing import AsyncGenerator, Generator, Generic, Optional, Tuple, TypeVar, Union

from vocode.streaming.models.agent import (
    AgentConfig,
    ChatGPTAgentConfig,
    LLMAgentConfig,
)
from vocode.streaming.models.model import TypedModel
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils.worker import (
    InterruptibleEvent,
    InterruptibleEventFactory,
    InterruptibleWorker,
)


class AgentResponseType(str, Enum):
    BASE = "agent_response_base"
    MESSAGE = "agent_response_message"
    STOP = "agent_response_stop"
    FILLER_AUDIO = "agent_response_filler_audio"


class AgentResponse(TypedModel, type=AgentResponseType.BASE.value):
    pass


class AgentResponseMessage(TypedModel, type=AgentResponseType.MESSAGE.value):
    message: str
    is_interruptible: bool = True


class AgentResponseStop(TypedModel, type=AgentResponseType.STOP.value):
    pass


class AgentResponseFillerAudio(TypedModel, type=AgentResponseType.FILLER_AUDIO.value):
    pass


AgentConfigType = TypeVar("AgentConfigType", bound=AgentConfig)


class AbstractAgent(Generic[AgentConfigType]):
    def __init__(self, agent_config: AgentConfigType):
        self.agent_config = agent_config

    def get_agent_config(self) -> AgentConfig:
        return self.agent_config

    def update_last_bot_message_on_cut_off(self, message: str):
        """Updates the last bot message in the conversation history when the human cuts off the bot's response."""
        pass

    def get_cut_off_response(self) -> str:
        assert isinstance(self.agent_config, LLMAgentConfig) or isinstance(
            self.agent_config, ChatGPTAgentConfig
        )
        assert self.agent_config.cut_off_response is not None
        on_cut_off_messages = self.agent_config.cut_off_response.messages
        assert len(on_cut_off_messages) > 0
        return random.choice(on_cut_off_messages).text


class BaseAgent(AbstractAgent[AgentConfigType], InterruptibleWorker):
    def __init__(
        self,
        agent_config: AgentConfigType,
        input_queue: asyncio.Queue[InterruptibleEvent[Transcription]],
        output_queue: asyncio.Queue[InterruptibleEvent[AgentResponse]],
        interruptible_event_factory: InterruptibleEventFactory,
    ):
        AbstractAgent.__init__(self, agent_config=agent_config)
        InterruptibleWorker.__init__(
            self,
            input_queue=input_queue,
            output_queue=output_queue,
            interruptible_event_factory=interruptible_event_factory,
        )


class RespondAgent(BaseAgent):
    async def process(self, item: InterruptibleEvent[Transcription]) -> None:
        return await super().process(item)

    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[Optional[str], bool]:
        raise NotImplementedError

    def generate_response(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> AsyncGenerator[str, None]:
        raise NotImplementedError
