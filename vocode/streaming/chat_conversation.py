from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
import typing
from typing import Any, Optional

from vocode.streaming.agent.base_agent import (
    AgentInput,
    AgentResponse,
    AgentResponseFillerAudio,
    AgentResponseGenerationComplete,
    AgentResponseMessage,
    AgentResponseStop,
    BaseAgent,
    TranscriptionAgentInput,
)
from vocode.streaming.agent.state_agent import StateAgent
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.state_agent_transcript import (
    JsonTranscript,
    StateAgentTranscript,
)
from vocode.streaming.models.transcript import Transcript
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils.conversation_logger_adapter import wrap_logger
from vocode.streaming.utils.worker import (
    AsyncQueueWorker,
    InterruptibleAgentResponseEvent,
    InterruptibleAgentResponseWorker,
    InterruptibleEvent,
    InterruptibleEventFactory,
)


class ChatConversation:
    class QueueingInterruptibleEventFactory(InterruptibleEventFactory):
        def __init__(self, conversation: "ChatConversation"):
            self.conversation = conversation

        def create_interruptible_event(
            self, payload: Any, is_interruptible: bool = True
        ) -> InterruptibleEvent[Any]:
            interruptible_event: InterruptibleEvent = (
                super().create_interruptible_event(payload, is_interruptible)
            )
            self.conversation.interruptible_events.put_nowait(interruptible_event)
            return interruptible_event

        def create_interruptible_agent_response_event(
            self,
            payload: Any,
            is_interruptible: bool = True,
            agent_response_tracker: Optional[asyncio.Event] = None,
        ) -> InterruptibleAgentResponseEvent:
            interruptible_event = super().create_interruptible_agent_response_event(
                payload,
                is_interruptible=is_interruptible,
                agent_response_tracker=agent_response_tracker,
            )
            self.conversation.interruptible_events.put_nowait(interruptible_event)
            return interruptible_event

    class PromptWorker(AsyncQueueWorker):
        def __init__(
            self,
            input_queue: asyncio.Queue[Transcription],
            output_queue: asyncio.Queue[InterruptibleEvent[AgentInput]],
            conversation: "ChatConversation",
            interruptible_event_factory: InterruptibleEventFactory,
            agent: StateAgent,
        ):
            super().__init__(input_queue, output_queue)
            self.input_queue = input_queue
            self.output_queue = output_queue
            self.conversation = conversation
            self.interruptible_event_factory = interruptible_event_factory
            self.conversation_id = conversation.conversation_id

        async def process(self, transcription: Transcription):
            # Strip the transcription message and log the time silent
            transcription.message = transcription.message

            # If the transcription message is empty, handle it accordingly
            if len(transcription.message) == 0:
                self.conversation.logger.debug("Ignoring empty transcription")
                self.conversation.agent_response_tracker.set()
                return
            event = self.interruptible_event_factory.create_interruptible_event(
                payload=TranscriptionAgentInput(
                    transcription=transcription,
                    affirmative_phrase=None,
                    conversation_id=self.conversation.conversation_id,
                    agent_response_tracker=self.conversation.agent_response_tracker,
                    # vonage_uuid=getattr(self.conversation, "vonage_uuid", None),
                    # twilio_sid=getattr(self.conversation, "twilio_sid", None),
                ),
            )
            # Place the event in the output queue for further processing
            self.produce_nonblocking(event)

    class AgentResponsesWorker(InterruptibleAgentResponseWorker):
        """Collects Agent Responses"""

        def __init__(
            self,
            input_queue: asyncio.Queue[InterruptibleAgentResponseEvent[AgentResponse]],
            output_queue: asyncio.Queue[InterruptibleAgentResponseEvent[BaseMessage]],
            conversation: "ChatConversation",
            interruptible_event_factory: InterruptibleEventFactory,
        ):
            super().__init__(input_queue, output_queue)
            self.input_queue = input_queue
            self.output_queue = output_queue
            self.conversation = conversation
            self.interruptible_event_factory = interruptible_event_factory

        async def process(self, item: InterruptibleAgentResponseEvent[AgentResponse]):
            try:
                agent_response = item.payload
                if isinstance(agent_response, AgentResponseFillerAudio):
                    return
                if isinstance(agent_response, AgentResponseStop):
                    self.conversation.logger.debug("Agent requested to stop")
                    item.agent_response_tracker.set()
                    await self.conversation.terminate()
                    return
                if isinstance(agent_response, AgentResponseGenerationComplete):
                    self.conversation.logger.debug("Agent response generation complete")
                    item.agent_response_tracker.set()
                    return
                agent_response_message = typing.cast(
                    AgentResponseMessage, agent_response
                )
                # get the prompt preamble
                if isinstance(self.conversation.agent, StateAgent):
                    agent_response_message.message.text = (
                        agent_response_message.message.text.strip()
                    )
                    self.conversation.logger.info(
                        f"Agent: {agent_response_message.message.text}"
                    )
                    if len(agent_response_message.message.text) > 0:
                        await self.output_queue.put(agent_response_message)
                        await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                self.conversation.logger.debug("Agent responses worker cancelled")
            except Exception as e:
                self.conversation.logger.error(f"Error in agent responses worker: {e}")

    def __init__(
        self,
        agent: BaseAgent,
        conversation_id: str,
        logger: logging.Logger,
        message_queue: Optional[queue.Queue[Transcription]] = None,
        agent_message_output_queue: Optional[queue.Queue[AgentResponseMessage]] = None,
    ):

        self.agent = agent
        self.conversation_id = conversation_id
        self.agent.conversation_id = conversation_id
        self.logger = wrap_logger(logger, conversation_id=conversation_id)
        self.stop_event = threading.Event()
        self.started_event = threading.Event()
        self.message_queue = message_queue or queue.Queue()
        self.agent_message_output_queue = agent_message_output_queue or queue.Queue()
        self.agent.attach_transcript(Transcript())
        self.interruptible_events: queue.Queue[InterruptibleEvent] = queue.Queue()
        self.interruptible_event_factory = self.QueueingInterruptibleEventFactory(
            conversation=self
        )
        self.agent.set_interruptible_event_factory(self.interruptible_event_factory)
        self.agent_response_tracker = asyncio.Event()
        self.prompt_worker = self.PromptWorker(
            conversation=self,
            agent=self.agent,
            input_queue=asyncio.Queue(),
            output_queue=self.agent.get_input_queue(),
            interruptible_event_factory=self.interruptible_event_factory,
        )

        self.agent_responses_worker = self.AgentResponsesWorker(
            conversation=self,
            input_queue=self.agent.get_output_queue(),
            output_queue=asyncio.Queue(),
            interruptible_event_factory=self.interruptible_event_factory,
        )

        # TODO Actions ...

        self.mark_last_action_timestamp()

        self.logger.debug("Conversation created")

    async def start(
        self,
        json_transcript: Optional[JsonTranscript] = None,
    ):
        self.logger.debug("Convo starting")
        self.prompt_worker.start()
        self.agent_responses_worker.start()
        self.logger.debug("Agent starting")
        self.agent.start()
        self.logger.debug("Agent started")
        self.logger.debug(
            f"Conversation Agent State: {self.agent.get_json_transcript()}"
        )

        # TODO Initial Message Logic.
        # initial_message = self.agent.get_agent_config().initial_message
        # call_type = self.agent.get_agent_config().call_type

        if json_transcript:
            self.agent.update_state_from_transcript(json_transcript)

        self.active = True

    async def receive_message(self, message: str):
        transcription = Transcription(
            message=message,
            confidence=1.0,
            is_final=True,
        )

        self.logger.debug(f"Received a message: {message}")
        self.logger.debug(
            f"Conversation Agent State: {self.agent.get_json_transcript()}"
        )
        self.agent_response_tracker.clear()
        await self.prompt_worker.input_queue.put(transcription)
        await self.agent_response_tracker.wait()

    def mark_last_action_timestamp(self):
        self.last_action_timestamp = time.time()

    async def broadcast_interrupt(self):
        """Stops all inflight events and cancels all workers that are sending output
        Returns true if any events were interrupted - which is used as a flag for the agent (is_interrupt)
        """
        self.logger.debug("Broadcasting interrupt")
        self.stop_event.set()
        num_interrupts = 0
        while True:
            try:
                interruptible_event = self.interruptible_events.get_nowait()
                if not interruptible_event.is_interrupted():
                    if interruptible_event.interrupt():
                        self.logger.debug("Interrupting event")
                        num_interrupts += 1
            except queue.Empty:
                break
        self.agent.clear_task_queue()
        self.agent_responses_worker.clear_task_queue()
        return num_interrupts > 0

    def mark_terminated(self):
        self.active = False

    async def terminate(self):
        self.mark_terminated()
        await self.broadcast_interrupt()
        self.logger.debug("Terminating Prompt Worker")
        self.prompt_worker.terminate()
        self.logger.debug("Terminating Agent Responses Worker")
        self.agent_responses_worker.terminate()
        self.logger.debug("Terminating Agent")
        self.agent.terminate()
        self.logger.debug("Successfully terminated")

    def is_active(self):
        return self.active
