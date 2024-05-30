from __future__ import annotations
from copy import deepcopy

import asyncio
from enum import Enum
import json
import math
import queue
import random
import threading
from typing import Any, Awaitable, Callable, Generic, Optional, Tuple, TypeVar, cast
import logging
import time
import typing
import requests
import aiohttp
from telephony_app.models.call_type import CallType
from vocode import getenv
from openai import AsyncOpenAI, OpenAI


from vocode.streaming.action.worker import ActionsWorker

from vocode.streaming.agent.bot_sentiment_analyser import (
    BotSentimentAnalyser,
)
from vocode.streaming.agent.command_agent import CommandAgent
from vocode.streaming.models.actions import ActionInput
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import (
    Message,
    Transcript,
    TranscriptCompleteEvent,
)
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.transcriber import EndpointingConfig, TranscriberConfig
from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.utils.conversation_logger_adapter import wrap_logger
from vocode.streaming.utils.events_manager import EventsManager
from vocode.streaming.utils.goodbye_model import GoodbyeModel

from vocode.streaming.models.agent import CommandAgentConfig, FillerAudioConfig
from vocode.streaming.models.synthesizer import (
    SentimentConfig,
)

from vocode.streaming.agent.utils import (
    format_openai_chat_messages_from_transcript,
    collate_response_async,
    openai_get_tokens,
    translate_message,
    vector_db_result_to_openai_chat_message,
)
from vocode.streaming.constants import (
    TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS,
    PER_CHUNK_ALLOWANCE_SECONDS,
    ALLOWED_IDLE_TIME,
    INCOMPLETE_SCALING_FACTOR,
    MAX_SILENCE_DURATION,
)
from vocode.streaming.agent.base_agent import (
    AgentInput,
    AgentResponse,
    AgentResponseFillerAudio,
    AgentResponseMessage,
    AgentResponseStop,
    AgentResponseType,
    BaseAgent,
    TranscriptionAgentInput,
)
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    FillerAudio,
)
from vocode.streaming.utils import create_conversation_id, get_chunk_size_per_second
from vocode.streaming.transcriber.base_transcriber import (
    Transcription,
    BaseTranscriber,
)
from vocode.streaming.utils.state_manager import ConversationStateManager
from vocode.streaming.utils.worker import (
    AsyncQueueWorker,
    InterruptibleAgentResponseWorker,
    InterruptibleEvent,
    InterruptibleEventFactory,
    InterruptibleAgentResponseEvent,
    InterruptibleWorker,
)

from telephony_app.utils.call_information_handler import update_call_transcripts

OutputDeviceType = TypeVar("OutputDeviceType", bound=BaseOutputDevice)


class BufferStatus(Enum):
    DISCARD = "discard"
    SEND = "send"
    HOLD = "hold"


class StreamingConversation(Generic[OutputDeviceType]):

    class QueueingInterruptibleEventFactory(InterruptibleEventFactory):
        def __init__(self, conversation: "StreamingConversation"):
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

    class TranscriptionBuffer:
        def __init__(self):
            self.buffer = []

        def to_message(self):
            return " ".join([word["word"] for word in self.buffer])

        def __str__(self):
            return str(self.buffer)

        def __len__(self):
            return len(self.buffer)

        def update_buffer(self, new_results, is_final):
            if not self.buffer:
                if is_final:
                    self.buffer = new_results
                return
            if is_final:
                self.buffer.extend(new_results)
            else:
                return

        def clear(self):
            self.buffer = []

    class TranscriptionsWorker(AsyncQueueWorker):
        """Processes all transcriptions: sends an interrupt if needed
        and sends final transcriptions to the output queue"""

        def __init__(
            self,
            input_queue: asyncio.Queue[Transcription],
            output_queue: asyncio.Queue[InterruptibleEvent[AgentInput]],
            conversation: "StreamingConversation",
            interruptible_event_factory: InterruptibleEventFactory,
            agent: BaseAgent,
        ):
            super().__init__(input_queue, output_queue)
            self.input_queue = input_queue
            self.output_queue = output_queue
            self.conversation = conversation
            self.interruptible_event_factory = interruptible_event_factory
            self.agent = agent
            self.buffer = self.conversation.TranscriptionBuffer()
            self.time_silent = 0.0
            self.buffer_avg_confidence = 0.0
            self.buffer_check_task: asyncio.Task = None
            self.block_inputs = True  # this flag controls if we are accepting new transcriptions, when true, the agent is speaking and we are not taking in new transcriptions
            self.silenceCache = (
                {}
            )  # this allows us not to reprocess endpoint classifications if it needs to be classified again in the event of a false interruption
            self.ready_to_send = BufferStatus.SEND
            self.synthesis_done = False
            self.current_sleep_time = 0.0
            self.last_classification = "good"
            self.last_filler_time = time.time()
            self.last_affirmative_time = time.time()
            self.vad_time = 2.0
            self.chosen_affirmative_phrase = None
            self.triggered_affirmative = False
            self.chosen_filler_phrase = None
            self.initial_message = None

        async def _buffer_check(self, initial_buffer: str):
            if (
                len(initial_buffer) == 0
            ):  # it might be empty if the its just started and no final one has been sent in
                return
            self.conversation.transcript.remove_last_human_message()
            # Reset the current sleep time to zero
            self.current_sleep_time = 0.0
            # Create a transcription object with the current buffer content
            transcription = Transcription(
                message=initial_buffer,
                confidence=1.0,  # We assume full confidence as it's not explicitly provided
                is_final=True,
                time_silent=self.time_silent,
            )
            current_phrase = self.chosen_affirmative_phrase
            # if self.conversation.agent.agent_config.pending_action == "pending":

            event = self.interruptible_event_factory.create_interruptible_event(
                payload=TranscriptionAgentInput(
                    transcription=transcription,
                    affirmative_phrase=current_phrase,
                    conversation_id=self.conversation.id,
                    vonage_uuid=getattr(self.conversation, "vonage_uuid", None),
                    twilio_sid=getattr(self.conversation, "twilio_sid", None),
                ),
            )
            # Place the event in the output queue for further processing
            self.output_queue.put_nowait(event)

            self.conversation.logger.info("Transcription event put in output queue")

            # Set the buffer status to HOLD, indicating we're not ready to send it yet
            self.ready_to_send = BufferStatus.HOLD

            self.conversation.logger.info(f"Marking as send")
            self.ready_to_send = BufferStatus.SEND
            # releast the action, if there is one
            self.conversation.agent.can_send = True
            return

        async def process(self, transcription: Transcription):
            # Ignore the transcription if we are currently in-flight (i.e., the agent is speaking)
            # log the current transcript
            if self.conversation.agent.block_inputs:
                self.conversation.logger.debug(
                    "Ignoring transcription since we are awaiting a tool call."
                )
                self.conversation.mark_last_action_timestamp()
                return
            if self.block_inputs and not self.agent.agent_config.allow_interruptions:
                self.conversation.logger.debug(
                    "Ignoring transcription since we are in-flight"
                )
                return

            # Mark the timestamp of the last action
            self.conversation.mark_last_action_timestamp()

            # If the message is just "vad", handle it without resetting the buffer check
            if transcription.message.strip() == "vad":

                if len(self.buffer) == 0:
                    self.conversation.logger.info("Ignoring vad, empty message.")
                    return

                # If a buffer check task is running, extend the current sleep time
                if self.buffer_check_task and not self.buffer_check_task.done():
                    self.conversation.logger.info(
                        "Adding waiting chunk to buffer check task due to VAD"
                    )

                    self.current_sleep_time = self.vad_time
                    self.vad_time = self.vad_time / 3
                    # when we wait more, they were silent so we want to push out a filler audio

                return
            if "words" not in json.loads(transcription.message):
                self.conversation.logger.info("Ignoring transcription, no words.")
                return
            elif len(json.loads(transcription.message)["words"]) == 0:
                # when we wait more, they were silent so we want to push out a filler audio
                self.conversation.logger.info("Ignoring transcription, zero words.")
                return

            self.conversation.logger.debug(
                f"Transcription message: {' '.join(word['word'] for word in json.loads(transcription.message)['words'])}"
            )
            if self.agent.agent_config.allow_interruptions:
                self.conversation.stop_event.set()  # slower more precise
                await self.conversation.output_device.clear()
                self.conversation.logger.info("Cleared the output device")

            # Strip the transcription message and log the time silent
            transcription.message = transcription.message
            self.conversation.logger.info(f"Time silent: {self.time_silent}s")

            # If the transcription message is empty, handle it accordingly
            if len(transcription.message) == 0:
                self.conversation.logger.debug("Ignoring empty transcription")
                if len(self.buffer) == 0:
                    self.conversation.logger.info("Ignoring empty message.")
                    return
                self.time_silent += transcription.time_silent
                return
            # Update the buffer with the new message if it contains new content and log it
            new_words = json.loads(transcription.message)["words"]

            self.buffer.update_buffer(new_words, transcription.is_final)
            # we also want to update the last user message

            self.vad_time = 2.0
            self.time_silent = transcription.time_silent

            # If a buffer check task exists, cancel it and start a new one
            if self.buffer_check_task:
                self.conversation.logger.info("Cancelling buffer check task")
                self.conversation.logger.info(
                    f"BufferCancel? {self.buffer_check_task.cancel()}"
                )
            # if there is an initial message, we're in outbound mode and we should say it right off
            if self.initial_message:
                asyncio.create_task(
                    self.conversation.send_initial_message(self.initial_message)
                )  # TODO: this seems like its hanging, why not await?
                self.initial_message = None
                return

            # Broadcast an interrupt and set the buffer status to DISCARD
            self.conversation.broadcast_interrupt()
            self.ready_to_send = BufferStatus.DISCARD

            # Start a new buffer check task to recalculate the timing
            self.buffer_check_task = asyncio.create_task(
                self._buffer_check(deepcopy(self.buffer.to_message()))
            )
            return

    class FillerAudioWorker(InterruptibleAgentResponseWorker):
        """
        - Waits for a configured number of seconds and then sends filler audio to the output
        - Exposes wait_for_filler_audio_to_finish() which the AgentResponsesWorker waits on before
          sending responses to the output queue
        """

        def __init__(
            self,
            input_queue: asyncio.Queue[InterruptibleAgentResponseEvent[FillerAudio]],
            conversation: "StreamingConversation",
        ):
            super().__init__(input_queue=input_queue)
            self.input_queue = input_queue
            self.conversation = conversation
            self.current_filler_seconds_per_chunk: Optional[int] = None
            self.filler_audio_started_event: Optional[threading.Event] = None

        async def wait_for_filler_audio_to_finish(self):
            if (
                self.filler_audio_started_event is None
                or not self.filler_audio_started_event.set()
            ):
                self.conversation.logger.debug(
                    "Not waiting for filler audio to finish since we didn't send any chunks"
                )
                return
            if self.interruptible_event and isinstance(
                self.interruptible_event, InterruptibleAgentResponseEvent
            ):
                await self.interruptible_event.agent_response_tracker.wait()

        def interrupt_current_filler_audio(self):
            return self.interruptible_event and self.interruptible_event.interrupt()

        async def process(self, item: InterruptibleAgentResponseEvent[FillerAudio]):
            try:

                filler_audio = item.payload
                assert self.conversation.filler_audio_config is not None
                filler_synthesis_result = filler_audio.create_synthesis_result()

                self.current_filler_seconds_per_chunk = filler_audio.seconds_per_chunk
                # tis a generator
                audio = bytearray()
                async for chunk in filler_synthesis_result.chunk_generator:
                    audio.extend(chunk.chunk)

                # await asyncio.sleep(silence_threshold)
                self.conversation.logger.debug("Sending filler audio to output")
                self.filler_audio_started_event = threading.Event()
                self.conversation.output_device.consume_nonblocking(
                    audio,
                )
                item.agent_response_tracker.set()
            except asyncio.CancelledError:
                pass

    class AgentResponsesWorker(InterruptibleAgentResponseWorker):
        """Runs Synthesizer.create_speech and sends the SynthesisResult to the output queue"""

        def __init__(
            self,
            input_queue: asyncio.Queue[InterruptibleAgentResponseEvent[AgentResponse]],
            output_queue: asyncio.Queue[
                InterruptibleAgentResponseEvent[Tuple[BaseMessage, SynthesisResult]]
            ],
            conversation: "StreamingConversation",
            interruptible_event_factory: InterruptibleEventFactory,
        ):
            super().__init__(
                input_queue=input_queue,
                output_queue=output_queue,
            )
            self.input_queue = input_queue
            self.output_queue = output_queue
            self.conversation = conversation
            self.interruptible_event_factory = interruptible_event_factory
            self.convoCache = {}
            self.chunk_size = (
                get_chunk_size_per_second(
                    self.conversation.synthesizer.get_synthesizer_config().audio_encoding,
                    self.conversation.synthesizer.get_synthesizer_config().sampling_rate,
                )
                * TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS
            )

        def send_filler_audio(self, agent_response_tracker: Optional[asyncio.Event]):
            # only send it if a digit isn't written out in the current transcription buffer
            digits = [
                "one",
                "two",
                "three",
                "four",
                "five",
                "six",
                "seven",
                "eight",
                "nine",
                "zero",
            ]
            if (
                sum(
                    self.conversation.transcriptions_worker.buffer.to_message().count(
                        digit
                    )
                    for digit in digits
                )
                < 4
            ) and sum(
                self.conversation.transcriptions_worker.buffer.to_message().count(digit)
                for digit in digits
            ) > 1:
                return
            self.conversation.logger.debug("Sending filler audio")
            if (
                self.conversation.synthesizer.filler_audios
                and self.conversation.filler_audio_worker is not None
            ):
                filler_audio = random.choice(
                    self.conversation.synthesizer.filler_audios
                )
                while (
                    filler_audio.message.text
                    == self.conversation.transcriptions_worker.chosen_filler_phrase
                ):
                    filler_audio = random.choice(
                        self.conversation.synthesizer.filler_audios
                    )
                self.conversation.transcriptions_worker.chosen_filler_phrase = (
                    filler_audio.message.text
                )
                self.conversation.logger.debug(f"Chose {filler_audio.message.text}")
                event = self.interruptible_event_factory.create_interruptible_agent_response_event(
                    filler_audio,
                    is_interruptible=filler_audio.is_interruptible,
                    agent_response_tracker=agent_response_tracker,
                )
                self.conversation.filler_audio_worker.consume_nonblocking(event)
            else:
                self.conversation.logger.debug(
                    "No filler audio available for synthesizer"
                )

        def send_affirmative_audio(
            self, agent_response_tracker: Optional[asyncio.Event], phrase: str
        ):
            # if there is a pending action, don't send
            if self.conversation.agent.agent_config.pending_action:
                return
            # only send it if a digit isn't written out in the current transcription buffer
            digits = [
                "one",
                "two",
                "three",
                "four",
                "five",
                "six",
                "seven",
                "eight",
                "nine",
                "zero",
                "ten",
                "twenty",
                "thirty",
                "forty",
                "fifty",
                "sixty",
                "seventy",
                "eighty",
                "ninety",
                "hundred",
            ]
            if (
                sum(
                    self.conversation.transcriptions_worker.buffer.to_message().count(
                        digit
                    )
                    for digit in digits
                )
                < 4
                and sum(
                    self.conversation.transcriptions_worker.buffer.to_message().count(
                        digit
                    )
                    for digit in digits
                )
                > 1
            ):
                return
            self.conversation.logger.debug("Sending affirmative audio")
            if (
                self.conversation.synthesizer.affirmative_audios
                and self.conversation.filler_audio_worker is not None
            ):
                affirmative_audio = None
                for audio in self.conversation.synthesizer.affirmative_audios:
                    if audio.message.text == phrase:
                        affirmative_audio = audio
                        break
                if not affirmative_audio:
                    self.conversation.logger.debug(
                        f"Phrase {phrase} not found in affirmative audios"
                    )
                    return
                self.conversation.logger.debug(
                    f"Chose {affirmative_audio.message.text}"
                )
                event = self.interruptible_event_factory.create_interruptible_agent_response_event(
                    affirmative_audio,
                    is_interruptible=affirmative_audio.is_interruptible,
                    agent_response_tracker=agent_response_tracker,
                )
                self.conversation.filler_audio_worker.consume_nonblocking(event)
            else:
                self.conversation.logger.debug(
                    "No filler audio available for synthesizer"
                )

        async def process(self, item: InterruptibleAgentResponseEvent[AgentResponse]):
            if not self.conversation.synthesis_enabled:
                self.conversation.logger.debug(
                    "Synthesis disabled, not synthesizing speech"
                )
                return
            try:
                agent_response = item.payload
                if isinstance(agent_response, AgentResponseFillerAudio):
                    self.send_filler_audio(item.agent_response_tracker)
                    return
                if isinstance(agent_response, AgentResponseStop):
                    self.conversation.logger.debug("Agent requested to stop")
                    item.agent_response_tracker.set()
                    await self.conversation.terminate()
                    return

                agent_response_message = typing.cast(
                    AgentResponseMessage, agent_response
                )

                if self.conversation.filler_audio_worker is not None:
                    if (
                        self.conversation.filler_audio_worker.interrupt_current_filler_audio()
                    ):
                        await self.conversation.filler_audio_worker.wait_for_filler_audio_to_finish()
                if not agent_response_message.message.text.strip() or not any(
                    char.isalpha() or char.isdigit()
                    for char in agent_response_message.message.text
                ):
                    self.conversation.logger.debug(
                        "SYNTH: Ignoring empty or non-letter agent response message"
                    )
                    return
                # get the prompt preamble
                if isinstance(self.conversation.agent, CommandAgent):
                    prompt_preamble = (
                        self.conversation.agent.agent_config.prompt_preamble
                    )

                    if not self.conversation.agent.agent_config.language.startswith(
                        "en"
                    ):
                        self.conversation.logger.debug(
                            f"Translating message from English to {self.conversation.agent.agent_config.language} {agent_response_message.message.text}"
                        )
                        translated_message = translate_message(
                            self.conversation.logger,
                            agent_response_message.message.text,
                            "en-US",
                            self.conversation.agent.agent_config.language,
                        )
                        current_message = agent_response_message.message.text + ""
                        agent_response_message.message.text = translated_message
                        synthesis_result = (
                            await self.conversation.synthesizer.create_speech(
                                agent_response_message.message,
                                self.chunk_size,
                                bot_sentiment=self.conversation.bot_sentiment,
                            )
                        )
                        replacer = "\n"
                        self.conversation.logger.info(
                            f"[{self.conversation.agent.agent_config.call_type}:{self.conversation.agent.agent_config.current_call_id}] Agent: {translated_message.replace(replacer, ' ')}"
                        )
                        agent_response_message.message.text = current_message
                    else:
                        self.conversation.logger.info(
                            f"[{self.conversation.agent.agent_config.call_type}:{self.conversation.agent.agent_config.current_call_id}] Agent: {agent_response_message.message.text}"
                        )
                        synthesis_result = (
                            await self.conversation.synthesizer.create_speech(
                                agent_response_message.message,
                                self.chunk_size,
                                bot_sentiment=self.conversation.bot_sentiment,
                            )
                        )
                    self.produce_interruptible_agent_response_event_nonblocking(
                        (agent_response_message.message, synthesis_result),
                        is_interruptible=item.is_interruptible,
                        agent_response_tracker=item.agent_response_tracker,
                    )
                else:
                    self.conversation.logger.debug(
                        f"SYNTH: WAS NOT COMMAND AGENT, {agent_response_message.message.text}"
                    )
            except asyncio.CancelledError:
                pass

    class SynthesisResultsWorker(InterruptibleAgentResponseWorker):
        """Worker class responsible for playing synthesized speech results.

        This worker takes synthesized speech results from the input queue and plays them
        on the output device. It also handles the creation of transcript messages and
        manages interruptible events related to speech output.
        """

        def __init__(
            self,
            input_queue: asyncio.Queue[
                InterruptibleAgentResponseEvent[Tuple[BaseMessage, SynthesisResult]]
            ],
            conversation: "StreamingConversation",
        ):
            # Initialize the worker with the input queue and the conversation context.
            super().__init__(input_queue=input_queue)
            self.input_queue = input_queue
            self.conversation = conversation

        async def process(
            self,
            item: InterruptibleAgentResponseEvent[Tuple[BaseMessage, SynthesisResult]],
        ):
            # Process a single item from the input queue.
            try:
                # Unpack the message and synthesis result from the event payload.
                message, synthesis_result = item.payload

                # Initialize a transcript message with an empty text, which will be updated later.
                transcript_message = Message(
                    text="",
                    sender=Sender.BOT,
                )
                # Add the empty transcript message to the conversation's transcript.
                self.conversation.transcript.add_message(
                    message=transcript_message,
                    conversation_id=self.conversation.id,
                    publish_to_events_manager=False,
                )

                # Prepare the coroutine for sending synthesized speech to the output device.
                send_speech_coroutine = self.conversation.send_speech_to_output(
                    message.text,
                    synthesis_result,
                    self.conversation.stop_event,
                    self.conversation.started_event,
                    TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS,
                    transcript_message=transcript_message,
                )

                # Create an asynchronous task for the coroutine and store it as the current task.
                self.current_task = asyncio.create_task(send_speech_coroutine)

                # Create an interruptible event for the current task, allowing it to be interrupted if necessary.
                interruptible_event = (
                    self.interruptible_event_factory.create_interruptible_event(
                        self.current_task,
                        is_interruptible=True,
                    )
                )

                # Place the interruptible event into the output queue for further processing.
                self.output_queue.put_nowait(interruptible_event)

                # Wait for the current task to complete or be cancelled.
                try:
                    # Await the completion of the speech output task and retrieve the message sent and cutoff status.
                    message_sent, cut_off = await self.current_task
                    self.conversation.started_event.clear()
                except Exception as e:
                    # If an exception occurs, log it and set the message as cut off.
                    self.conversation.logger.debug(f"Detected Task cancelled: {e}")
                    message_sent, cut_off = "", True
                    return

                # Once the speech output is complete, publish the transcript message with the actual content spoken.
                transcript_message.text = transcript_message.text.replace("Err...", "")
                # split on < and truncate there
                transcript_message.text = transcript_message.text.split("<")[0].strip()
                self.conversation.transcript.maybe_publish_transcript_event_from_message(
                    message=transcript_message,
                    conversation_id=self.conversation.id,
                )
                # Signal that the agent response has been processed.
                item.agent_response_tracker.set()
                # Log the message that was successfully sent.
                self.conversation.logger.debug(f"Message sent: {message_sent}")

                # Check if the conversation should end after the agent says goodbye.
                if self.conversation.agent.agent_config.end_conversation_on_goodbye:
                    # Create a task to detect if the agent said goodbye.
                    goodbye_detected_task = (
                        self.conversation.agent.create_goodbye_detection_task(
                            message_sent
                        )
                    )
                    try:
                        # Wait briefly for the goodbye detection task to complete.
                        if await asyncio.wait_for(goodbye_detected_task, 0.1):
                            # If goodbye was detected, log the event and terminate the conversation.
                            self.conversation.logger.debug(
                                "Agent said goodbye, ending call"
                            )
                            await self.conversation.terminate()
                    except asyncio.TimeoutError:
                        # If the goodbye detection task times out, simply pass.
                        pass
            except asyncio.CancelledError:
                # If the task was cancelled, do nothing.
                pass

    def __init__(
        self,
        output_device: OutputDeviceType,
        transcriber: BaseTranscriber[TranscriberConfig],
        agent: BaseAgent,
        synthesizer: BaseSynthesizer,
        conversation_id: Optional[str] = None,
        per_chunk_allowance_seconds: float = PER_CHUNK_ALLOWANCE_SECONDS,
        events_manager: Optional[EventsManager] = None,
        logger: Optional[logging.Logger] = None,
    ):

        self.id = conversation_id or create_conversation_id()
        self.logger = wrap_logger(
            logger or logging.getLogger(__name__),
            conversation_id=self.id,
        )
        # threadingevent
        self.stop_event = threading.Event()
        self.started_event = threading.Event()
        self.output_device = output_device
        self.transcriber = transcriber
        self.agent = agent
        self.synthesizer = synthesizer
        self.synthesis_enabled = True

        self.interruptible_events: queue.Queue[InterruptibleEvent] = queue.Queue()
        self.interruptible_event_factory = self.QueueingInterruptibleEventFactory(
            conversation=self
        )
        self.agent.set_interruptible_event_factory(self.interruptible_event_factory)
        self.synthesis_results_queue: asyncio.Queue[
            InterruptibleAgentResponseEvent[Tuple[BaseMessage, SynthesisResult]]
        ] = asyncio.Queue()
        self.filler_audio_queue: asyncio.Queue[
            InterruptibleAgentResponseEvent[FillerAudio]
        ] = asyncio.Queue()
        self.state_manager = self.create_state_manager()
        self.transcriptions_worker = self.TranscriptionsWorker(
            input_queue=self.transcriber.output_queue,
            output_queue=self.agent.get_input_queue(),
            conversation=self,
            interruptible_event_factory=self.interruptible_event_factory,
            agent=self.agent,
        )
        self.agent.attach_conversation_state_manager(self.state_manager)
        self.agent_responses_worker = self.AgentResponsesWorker(
            input_queue=self.agent.get_output_queue(),
            output_queue=self.synthesis_results_queue,
            conversation=self,
            interruptible_event_factory=self.interruptible_event_factory,
        )
        self.actions_worker = None
        if self.agent.get_agent_config().actions:
            self.actions_worker = ActionsWorker(
                input_queue=self.agent.actions_queue,
                output_queue=self.agent.get_input_queue(),
                interruptible_event_factory=self.interruptible_event_factory,
                action_factory=self.agent.action_factory,
            )
            self.actions_worker.attach_conversation_state_manager(self.state_manager)
        self.synthesis_results_worker = self.SynthesisResultsWorker(
            input_queue=self.synthesis_results_queue, conversation=self
        )
        self.filler_audio_worker = None
        self.filler_audio_config: Optional[FillerAudioConfig] = None
        if self.agent.get_agent_config().use_filler_words:
            self.filler_audio_worker = self.FillerAudioWorker(
                input_queue=self.filler_audio_queue, conversation=self
            )

        self.events_manager = events_manager or EventsManager()
        self.events_task: Optional[asyncio.Task] = None
        self.per_chunk_allowance_seconds = per_chunk_allowance_seconds
        self.transcript = Transcript()
        self.transcript.attach_events_manager(self.events_manager)
        self.bot_sentiment = None
        if self.agent.get_agent_config().track_bot_sentiment:
            self.sentiment_config = (
                self.synthesizer.get_synthesizer_config().sentiment_config
            )
            if not self.sentiment_config:
                self.sentiment_config = SentimentConfig()
            self.bot_sentiment_analyser = BotSentimentAnalyser(
                emotions=self.sentiment_config.emotions
            )

        self.is_human_speaking = False
        self.active = False
        self.mark_last_action_timestamp()

        self.check_for_idle_task: Optional[asyncio.Task] = None
        self.track_bot_sentiment_task: Optional[asyncio.Task] = None

        self.current_transcription_is_interrupt: bool = False

        # tracing
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

    def create_state_manager(self) -> ConversationStateManager:
        return ConversationStateManager(conversation=self)

    async def start(self, mark_ready: Optional[Callable[[], Awaitable[None]]] = None):
        self.transcriber.start()
        if self.agent.get_agent_config().call_type == CallType.INBOUND:
            self.transcriber.mute()
        self.transcriptions_worker.start()
        self.agent_responses_worker.start()
        self.synthesis_results_worker.start()
        self.output_device.start()
        if self.filler_audio_worker is not None:
            self.filler_audio_worker.start()
        if self.actions_worker is not None:
            self.actions_worker.start()
        is_ready = await self.transcriber.ready()
        if not is_ready:
            raise Exception("Transcriber startup failed")

        if self.agent.get_agent_config().use_filler_words:
            self.filler_audio_config = FillerAudioConfig()
            filler_audio_task = asyncio.create_task(
                self.synthesizer.set_filler_audios(self.filler_audio_config)
            )
            affirmative_audio_task = asyncio.create_task(
                self.synthesizer.set_affirmative_audios(self.filler_audio_config)
            )

            await asyncio.gather(filler_audio_task, affirmative_audio_task)

        self.agent.start()
        if isinstance(self.agent, CommandAgent):
            self.agent.conversation_id = self.id
            self.agent.twilio_sid = getattr(self, "twilio_sid", None)
        initial_message = self.agent.get_agent_config().initial_message
        call_type = self.agent.get_agent_config().call_type
        self.agent.attach_transcript(self.transcript)

        if initial_message and call_type == CallType.INBOUND:
            asyncio.create_task(
                self.send_initial_message(initial_message)
            )  # TODO: this seems like its hanging, why not await?
        elif initial_message and call_type == CallType.OUTBOUND:
            self.transcriptions_worker.initial_message = initial_message
        else:
            self.logger.debug("ERROR: INVALID CALL TYPE")
        if mark_ready:
            await mark_ready()
        if self.synthesizer.get_synthesizer_config().sentiment_config:
            await self.update_bot_sentiment()
        self.active = True
        if self.synthesizer.get_synthesizer_config().sentiment_config:
            self.track_bot_sentiment_task = asyncio.create_task(
                self.track_bot_sentiment()
            )
        self.check_for_idle_task = asyncio.create_task(self.check_for_idle())
        if len(self.events_manager.subscriptions) > 0:
            self.events_task = asyncio.create_task(self.events_manager.start())
        # set transcriber is final to false
        self.transcriptions_worker.block_inputs = False

    async def send_initial_message(self, initial_message: BaseMessage):
        # TODO: configure if initial message is interruptible
        initial_message_tracker = asyncio.Event()
        agent_response_event = (
            self.interruptible_event_factory.create_interruptible_agent_response_event(
                AgentResponseMessage(message=initial_message),
                is_interruptible=False,
                agent_response_tracker=initial_message_tracker,
            )
        )
        self.agent_responses_worker.consume_nonblocking(agent_response_event)
        await initial_message_tracker.wait()
        self.transcriber.unmute()

    async def check_for_idle(self):
        """Terminates the conversation after 15 seconds if no activity is detected"""
        while self.is_active():
            if time.time() - self.last_action_timestamp > 30:
                self.logger.debug("Conversation idle for too long, terminating")
                await self.terminate()
                return
            await asyncio.sleep(1)

    async def track_bot_sentiment(self):
        """Updates self.bot_sentiment every second based on the current transcript"""
        prev_transcript = None
        while self.is_active():
            await asyncio.sleep(1)
            if self.transcript.to_string() != prev_transcript:
                await self.update_bot_sentiment()
                prev_transcript = self.transcript.to_string()

    async def update_bot_sentiment(self):
        new_bot_sentiment = await self.bot_sentiment_analyser.analyse(
            self.transcript.to_string()
        )
        if new_bot_sentiment.emotion:
            self.logger.debug("Bot sentiment: %s", new_bot_sentiment)
            self.bot_sentiment = new_bot_sentiment

    def receive_message(self, message: str):
        transcription = Transcription(
            message=message,
            confidence=1.0,
            is_final=True,
        )
        if (
            self.transcriptions_worker.block_inputs
            and not self.agent.agent_config.allow_interruptions
        ):

            return
        self.transcriptions_worker.consume_nonblocking(transcription)

    def receive_audio(self, chunk: bytes):
        self.transcriber.send_audio(chunk)

    def warmup_synthesizer(self):
        self.synthesizer.ready_synthesizer()

    def mark_last_action_timestamp(self):
        self.last_action_timestamp = time.time()

    def broadcast_interrupt(self):
        """Stops all inflight events and cancels all workers that are sending output

        Returns true if any events were interrupted - which is used as a flag for the agent (is_interrupt)
        """
        self.logger.debug("Broadcasting interrupt")

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
        self.transcriber.unmute()
        self.transcriptions_worker.block_inputs = False
        self.agent.clear_task_queue()
        self.agent_responses_worker.clear_task_queue()
        if not self.agent.get_agent_config().allow_interruptions:
            self.synthesis_results_worker.clear_task_queue()
        return num_interrupts > 0

    def is_interrupt(self, transcription: Transcription):
        return transcription.confidence >= (
            self.transcriber.get_transcriber_config().min_interrupt_confidence or 0
        )

    async def send_speech_to_output(
        self,
        message: str,
        synthesis_result: SynthesisResult,
        stop_event: threading.Event,
        started_event: threading.Event,
        seconds_per_chunk: int,
        transcript_message: Optional[Message] = None,
    ):
        # Check if both the synthesis result and message are available, if not, return empty message and False flag
        if not (synthesis_result and message):
            return "", False
        # reset the stop event
        stop_event.clear()

        """
        - Sends the speech chunk by chunk to the output device
        - update the transcript message as chunks come in (transcript_message is always provided for non filler audio utterances)
        - If the stop_event is set, the output is stopped
        - Sets started_event when the first chunk is sent
        """
        # Set the flag indicating that synthesis is not yet complete
        self.transcriptions_worker.synthesis_done = False

        # Mute the transcriber during speech synthesis if configured to do so
        if self.transcriber.get_transcriber_config().mute_during_speech:
            self.logger.debug("Muting transcriber")

        # Initialize variables to hold the message sent and the cutoff status
        message_sent = message
        cut_off = False

        # Calculate the size of each speech chunk based on the seconds per chunk and the audio configuration
        chunk_size = seconds_per_chunk * get_chunk_size_per_second(
            self.synthesizer.get_synthesizer_config().audio_encoding,
            self.synthesizer.get_synthesizer_config().sampling_rate,
        )

        # Initialize a bytearray to accumulate the speech data
        speech_data = bytearray()
        held_buffer = self.transcriptions_worker.buffer.to_message()
        # Asynchronously generate speech data from the synthesis result
        buffer_cleared = False
        async for chunk_result in synthesis_result.chunk_generator:
            if len(speech_data) > chunk_size:
                self.transcriptions_worker.synthesis_done = True
                started_event.set()
            if stop_event.is_set() and self.agent.agent_config.allow_interruptions:
                return "", False
            if len(speech_data) > chunk_size:
                self.transcriptions_worker.block_inputs = True
                self.transcriptions_worker.time_silent = 0.0
                self.transcriptions_worker.triggered_affirmative = False
                self.logger.debug(
                    f"Sending in synth buffer early, len {len(speech_data)}"
                )
                if self.agent.agent_config.allow_interruptions:
                    self.mark_last_action_timestamp()
                    for _ in range(1):
                        # Check if the stop event is set before sending each piece
                        if stop_event.is_set():
                            return "", False
                        # Calculate the size of each piece
                        piece_size = len(speech_data) // 1
                        # Send the piece to the output device
                        await self.output_device.consume_nonblocking(
                            speech_data[:piece_size]
                        )
                        # Remove the sent piece from the speech data
                        speech_data = speech_data[piece_size:]
                        # Sleep for a tenth of the chunk duration
                        await asyncio.sleep(seconds_per_chunk / 1)
                    if not buffer_cleared and not stop_event.is_set():
                        buffer_cleared = True
                        self.transcriptions_worker.buffer.clear()
                else:
                    self.transcriptions_worker.buffer.clear()
                    self.mark_last_action_timestamp()
                    await self.output_device.consume_nonblocking(speech_data)
                    speech_data = bytearray()
                    # sleep for the length of the speech
                    await asyncio.sleep(seconds_per_chunk)
                    if not buffer_cleared:
                        buffer_cleared = True
                        self.transcriptions_worker.buffer.clear()

            speech_data.extend(chunk_result.chunk)

        self.transcriptions_worker.synthesis_done = True

        # If a buffer check task exists, wait for it to complete before proceeding
        if self.transcriptions_worker.buffer_check_task:
            try:
                await self.transcriptions_worker.buffer_check_task
                # Handle cancellation of the buffer check task
                if self.transcriptions_worker.buffer_check_task.cancelled():
                    self.logger.debug("Buffer check task was cancelled.")
                    return "", False

            except asyncio.CancelledError:
                # Handle external cancellation of the buffer check task
                self.logger.debug(
                    "Buffer check task was cancelled by an external event."
                )
                return "", False
        else:
            # Proceed if no buffer check task is found
            self.logger.debug("No buffer check task found, proceeding without waiting.")

        # Log the start of sending synthesized speech to the output device
        self.logger.debug("Sending in synth buffer")
        # Clear the transcription worker's buffer and related attributes before sending
        self.transcriptions_worker.block_inputs = True
        self.transcriptions_worker.time_silent = 0.0
        self.transcriptions_worker.triggered_affirmative = False
        self.transcriptions_worker.buffer.clear()

        # Send the generated speech data to the output device
        start_time = time.time()
        if len(speech_data) > 0:
            await self.output_device.consume_nonblocking(speech_data)
        end_time = time.time()

        # Calculate the length of the speech in seconds
        speech_length_seconds = len(speech_data) / chunk_size
        # if held_buffer and len(held_buffer.strip()) > 0:
        #     self.logger.info(
        #         f"[{self.agent.agent_config.call_type}:{self.agent.agent_config.current_call_id}] Lead:{held_buffer}"
        #     )
        last_agent_message = next(
            (
                message["content"]
                for message in reversed(
                    format_openai_chat_messages_from_transcript(self.transcript)
                )
                if message["role"] == "assistant" and len(message["content"]) > 0
            ),
            None,
        )
        # Sleep for the duration of the speech minus the time already spent sending the data
        sleep_time = max(
            speech_length_seconds
            - (end_time - start_time)
            - self.per_chunk_allowance_seconds,
            0,
        )

        await asyncio.sleep(sleep_time)

        # Log the successful sending of speech data
        self.logger.debug(f"Sent speech data with size {len(speech_data)}")

        # Update the last action timestamp after sending speech
        self.mark_last_action_timestamp()

        # Update the message sent with the actual content spoken
        message_sent = synthesis_result.get_message_up_to(len(speech_data) / chunk_size)

        # If a transcript message is provided, update its text with the message sent
        if transcript_message:
            transcript_message.text = message_sent
        cut_off = False

        # Reset the synthesis done flag and prepare for the next synthesis
        self.transcriptions_worker.synthesis_done = False

        # Reset the transcription worker's flags and buffer status
        # check if there is more in the queue making this one be called again, if so, dont unblock
        if (
            self.agent_responses_worker.input_queue.qsize() == 0
            and self.agent_responses_worker.output_queue.qsize() == 0
            and self.agent.get_input_queue().qsize() == 0
            and self.agent.get_output_queue().qsize() == 0
            # it must also end in punctuation
        ):
            if message_sent and message_sent.strip()[-1] not in [","]:

                self.logger.info(f"Responding to {held_buffer}")
                self.transcriptions_worker.block_inputs = False
                # Unmute the transcriber after speech synthesis if it was muted
                if self.transcriber.get_transcriber_config().mute_during_speech:
                    self.logger.debug("Unmuting transcriber")
                    self.transcriber.unmute()
        self.transcriptions_worker.ready_to_send = BufferStatus.DISCARD

        # Return the message sent and the cutoff status
        return message_sent, cut_off

    def mark_terminated(self):
        self.active = False

    async def terminate(self):
        self.mark_terminated()
        self.broadcast_interrupt()
        if self.synthesis_results_worker.current_task:
            self.synthesis_results_worker.current_task.cancel()
        self.events_manager.publish_event(
            TranscriptCompleteEvent(conversation_id=self.id, transcript=self.transcript)
        )
        if self.check_for_idle_task:
            self.logger.debug("Terminating check_for_idle Task")
            self.check_for_idle_task.cancel()
        if self.track_bot_sentiment_task:
            self.logger.debug("Terminating track_bot_sentiment Task")
            self.track_bot_sentiment_task.cancel()
        if self.events_manager and self.events_task:
            self.logger.debug("Terminating events Task")
            await self.events_manager.flush()
        self.logger.debug("Tearing down synthesizer")
        await self.synthesizer.tear_down()
        self.logger.debug("Terminating agent")
        if (
            isinstance(self.agent, CommandAgent)
            and self.agent.agent_config.vector_db_config
        ):
            # Shutting down the vector db should be done in the agent's terminate method,
            # but it is done here because `vector_db.tear_down()` is async and
            # `agent.terminate()` is not async.
            self.logger.debug("Terminating vector db")
            await self.agent.vector_db.tear_down()
        self.agent.terminate()
        self.logger.debug("Terminating output device")
        self.output_device.terminate()
        self.logger.debug("Terminating speech transcriber")
        self.transcriber.terminate()
        self.logger.debug("Terminating transcriptions worker")
        self.transcriptions_worker.terminate()
        self.logger.debug("Terminating final transcriptions worker")
        self.agent_responses_worker.terminate()
        self.logger.debug("Terminating synthesis results worker")
        self.synthesis_results_worker.terminate()
        if self.filler_audio_worker is not None:
            self.logger.debug("Terminating filler audio worker")
            self.filler_audio_worker.terminate()
        if self.actions_worker is not None:
            self.logger.debug("Terminating actions worker")
            self.actions_worker.terminate()
        self.logger.debug("Successfully terminated")

    def is_active(self):
        return self.active
