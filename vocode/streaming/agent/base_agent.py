from __future__ import annotations

import asyncio
from enum import Enum
import logging
import random
from typing import AsyncGenerator, Generator, Generic, Optional, Tuple, TypeVar, Union
import typing
from opentelemetry import trace
from opentelemetry.trace import Span
from vocode.streaming.models.actions import ActionOutput

from vocode.streaming.models.agent import (
    AgentConfig,
    ChatGPTAgentConfig,
    LLMAgentConfig,
)
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.model import BaseModel, TypedModel
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils import remove_non_letters_digits
from vocode.streaming.utils.goodbye_model import GoodbyeModel
from vocode.streaming.models.transcript import Transcript
from vocode.streaming.utils.state_manager import ConversationStateManager
from vocode.streaming.utils.worker import (
    InterruptibleEvent,
    InterruptibleEventFactory,
    InterruptibleWorker,
)

tracer = trace.get_tracer(__name__)
AGENT_TRACE_NAME = "agent"


class AgentInputType(str, Enum):
    BASE = "agent_input_base"
    TRANSCRIPTION = "agent_input_transcription"
    ACTION_RESULT = "agent_input_action_result"


class AgentInput(TypedModel, type=AgentInputType.BASE.value):
    conversation_id: str
    vonage_uuid: Optional[str]
    twilio_sid: Optional[str]


class TranscriptionAgentInput(AgentInput, type=AgentInputType.TRANSCRIPTION.value):
    transcription: Transcription


class ActionResultAgentInput(AgentInput, type=AgentInputType.ACTION_RESULT.value):
    action_output: ActionOutput


class AgentResponseType(str, Enum):
    BASE = "agent_response_base"
    MESSAGE = "agent_response_message"
    STOP = "agent_response_stop"
    FILLER_AUDIO = "agent_response_filler_audio"


class AgentResponse(TypedModel, type=AgentResponseType.BASE.value):
    pass


class AgentResponseMessage(AgentResponse, type=AgentResponseType.MESSAGE.value):
    message: BaseMessage
    is_interruptible: bool = True


class AgentResponseStop(AgentResponse, type=AgentResponseType.STOP.value):
    pass


class AgentResponseFillerAudio(
    AgentResponse, type=AgentResponseType.FILLER_AUDIO.value
):
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
        ), "Set cutoff response is only implemented in LLMAgent and ChatGPTAgent"
        assert self.agent_config.cut_off_response is not None
        on_cut_off_messages = self.agent_config.cut_off_response.messages
        assert len(on_cut_off_messages) > 0
        return random.choice(on_cut_off_messages).text


class BaseAgent(AbstractAgent[AgentConfigType], InterruptibleWorker):
    def __init__(
        self,
        agent_config: AgentConfigType,
        interruptible_event_factory: InterruptibleEventFactory = InterruptibleEventFactory(),
        logger: Optional[logging.Logger] = None,
    ):
        self.input_queue: asyncio.Queue[
            InterruptibleEvent[AgentInput]
        ] = asyncio.Queue()
        self.output_queue: asyncio.Queue[
            InterruptibleEvent[AgentResponse]
        ] = asyncio.Queue()
        AbstractAgent.__init__(self, agent_config=agent_config)
        InterruptibleWorker.__init__(
            self,
            input_queue=self.input_queue,
            output_queue=self.output_queue,
            interruptible_event_factory=interruptible_event_factory,
        )
        self.logger = logger or logging.getLogger(__name__)
        self.goodbye_model = None
        if self.agent_config.end_conversation_on_goodbye:
            self.goodbye_model = GoodbyeModel()
            self.goodbye_model_initialize_task = asyncio.create_task(
                self.goodbye_model.initialize_embeddings()
            )
        self.transcript: Optional[Transcript] = None

    def attach_transcript(self, transcript: Transcript):
        self.transcript = transcript

    def attach_conversation_state_manager(
        self, conversation_state_manager: ConversationStateManager
    ):
        self.conversation_state_manager = conversation_state_manager

    def start(self):
        super().start()
        if self.agent_config.initial_message is not None:
            self.produce_interruptible_event_nonblocking(
                AgentResponseMessage(message=self.agent_config.initial_message),
                is_interruptible=False,
            )

    def set_interruptible_event_factory(self, factory: InterruptibleEventFactory):
        self.interruptible_event_factory = factory

    def get_input_queue(
        self,
    ) -> asyncio.Queue[InterruptibleEvent[AgentInput]]:
        return self.input_queue

    def get_output_queue(self) -> asyncio.Queue[InterruptibleEvent[AgentResponse]]:
        return self.output_queue

    def create_goodbye_detection_task(self, message: str) -> asyncio.Task:
        assert self.goodbye_model is not None
        return asyncio.create_task(self.goodbye_model.is_goodbye(message))


class RespondAgent(BaseAgent[AgentConfigType]):
    async def handle_generate_response(
        self, transcription: Transcription, conversation_id: str
    ) -> bool:
        tracer_name_start = await self.get_tracer_name_start()
        agent_span = tracer.start_span(
            f"{tracer_name_start}.generate_total"  # type: ignore
        )
        agent_span_first = tracer.start_span(
            f"{tracer_name_start}.generate_first"  # type: ignore
        )
        responses = self.generate_response(
            transcription.message,
            is_interrupt=transcription.is_interrupt,
            conversation_id=conversation_id,
        )
        is_first_response = True
        async for response in responses:
            if is_first_response:
                agent_span_first.end()
                is_first_response = False
            self.produce_interruptible_event_nonblocking(
                AgentResponseMessage(message=BaseMessage(text=response)),
                is_interruptible=self.agent_config.allow_agent_to_be_cut_off,
            )
        # TODO: implement should_stop for generate_responses
        agent_span.end()
        return False

    async def handle_respond(
        self, transcription: Transcription, conversation_id: str
    ) -> bool:
        try:
            tracer_name_start = await self.get_tracer_name_start()
            with tracer.start_as_current_span(f"{tracer_name_start}.respond_total"):
                response, should_stop = await self.respond(
                    transcription.message,
                    is_interrupt=transcription.is_interrupt,
                    conversation_id=conversation_id,
                )
        except Exception as e:
            self.logger.error(f"Error while generating response: {e}", exc_info=True)
            response = None
            return True
        if response:
            self.produce_interruptible_event_nonblocking(
                AgentResponseMessage(message=BaseMessage(text=response)),
                is_interruptible=self.agent_config.allow_agent_to_be_cut_off,
            )
            return should_stop
        else:
            self.logger.debug("No response generated")
        return False

    async def process(self, item: InterruptibleEvent[AgentInput]):
        assert self.transcript is not None
        try:
            agent_input = item.payload
            if agent_input.type != AgentInputType.TRANSCRIPTION:
                return
            transcription = typing.cast(
                TranscriptionAgentInput, agent_input
            ).transcription
            self.transcript.add_human_message(
                text=transcription.message,
                conversation_id=agent_input.conversation_id,
            )
            goodbye_detected_task = None
            if self.agent_config.end_conversation_on_goodbye:
                goodbye_detected_task = self.create_goodbye_detection_task(
                    transcription.message
                )
            if self.agent_config.send_filler_audio:
                self.produce_interruptible_event_nonblocking(AgentResponseFillerAudio())
            self.logger.debug("Responding to transcription")
            should_stop = False
            if self.agent_config.generate_responses:
                should_stop = await self.handle_generate_response(
                    transcription, agent_input.conversation_id
                )
            else:
                should_stop = await self.handle_respond(
                    transcription, agent_input.conversation_id
                )
            if should_stop:
                self.logger.debug("Agent requested to stop")
                self.produce_interruptible_event_nonblocking(AgentResponseStop())
                return
            if goodbye_detected_task:
                try:
                    goodbye_detected = await asyncio.wait_for(
                        goodbye_detected_task, 0.1
                    )
                    if goodbye_detected:
                        self.logger.debug("Goodbye detected, ending conversation")
                        self.produce_interruptible_event_nonblocking(
                            AgentResponseStop()
                        )
                        return
                except asyncio.TimeoutError:
                    self.logger.debug("Goodbye detection timed out")
        except asyncio.CancelledError:
            pass

    async def get_tracer_name_start(self) -> str:
        if hasattr(self, "tracer_name_start"):
            return self.tracer_name_start
        if (
            hasattr(self.agent_config, "azure_params")
            and self.agent_config.azure_params is not None
        ):
            beginning_agent_name = self.agent_config.type.rsplit("_", 1)[0]
            engine = self.agent_config.azure_params.engine
            tracer_name_start = (
                f"{AGENT_TRACE_NAME}.{beginning_agent_name}_azuregpt-{engine}"
            )
        else:
            optional_model_name = (
                f"-{self.agent_config.model_name}"
                if hasattr(self.agent_config, "model_name")
                else ""
            )
            tracer_name_start = remove_non_letters_digits(
                f"{AGENT_TRACE_NAME}.{self.agent_config.type}{optional_model_name}"
            )
        self.tracer_name_start: str = tracer_name_start
        return tracer_name_start

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
