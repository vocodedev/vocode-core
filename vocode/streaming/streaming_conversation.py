from __future__ import annotations

import asyncio
import json
import logging
import math
import queue
import random
import threading
import time
import typing
from copy import deepcopy
from enum import Enum
from typing import Any, Awaitable, Callable, Generic, Optional, Tuple, TypeVar, cast

import aiohttp
import httpx
import numpy
import requests
from openai import AsyncOpenAI, OpenAI
from vocode import getenv
from vocode.streaming.action.worker import ActionsWorker
from vocode.streaming.agent.base_agent import (
    AgentInput,
    AgentResponse,
    AgentResponseFillerAudio,
    AgentResponseGenerationComplete,
    AgentResponseMessage,
    AgentResponseStop,
    AgentResponseType,
    BaseAgent,
    TranscriptionAgentInput,
)
from vocode.streaming.agent.bot_sentiment_analyser import BotSentimentAnalyser
from vocode.streaming.agent.command_agent import CommandAgent
from vocode.streaming.agent.state_agent import StateAgent
from vocode.streaming.agent.utils import (
    collate_response_async,
    format_openai_chat_messages_from_transcript,
    openai_get_tokens,
    translate_message,
    vector_db_result_to_openai_chat_message,
)
from vocode.streaming.constants import (
    ALLOWED_IDLE_TIME,
    INCOMPLETE_SCALING_FACTOR,
    MAX_SILENCE_DURATION,
    PER_CHUNK_ALLOWANCE_SECONDS,
    TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS,
)
from vocode.streaming.models.actions import ActionInput
from vocode.streaming.models.agent import CommandAgentConfig, FillerAudioConfig
from vocode.streaming.models.events import Sender
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import SentimentConfig
from vocode.streaming.models.transcriber import EndpointingConfig, TranscriberConfig
from vocode.streaming.models.transcript import (
    Message,
    Transcript,
    TranscriptCompleteEvent,
)
from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    FillerAudio,
    SynthesisResult,
)
from vocode.streaming.transcriber.base_transcriber import BaseTranscriber, Transcription
from vocode.streaming.utils import create_conversation_id, get_chunk_size_per_second
from vocode.streaming.utils.conversation_logger_adapter import wrap_logger
from vocode.streaming.utils.events_manager import EventsManager
from vocode.streaming.utils.goodbye_model import GoodbyeModel
from vocode.streaming.utils.setup_tracer import (
    end_span,
    setup_tracer,
    span_event,
    start_span_in_ctx,
)
from vocode.streaming.utils.state_manager import ConversationStateManager
from vocode.streaming.utils.worker import (
    AsyncQueueWorker,
    InterruptibleAgentResponseEvent,
    InterruptibleAgentResponseWorker,
    InterruptibleEvent,
    InterruptibleEventFactory,
    InterruptibleWorker,
)

from telephony_app.models.call_type import CallType
from telephony_app.utils.call_information_handler import update_call_transcripts

tracer = setup_tracer()

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
            self.vad_detected = False
            self.first_message_lock = False

        async def _buffer_check(self, initial_buffer: str):
            try:
                if len(initial_buffer) == 0:
                    return
                self.conversation.transcript.remove_last_human_message()
                self.current_sleep_time = 0.0
                transcription = Transcription(
                    message=initial_buffer,
                    confidence=1.0,
                    is_final=True,
                    time_silent=self.time_silent,
                )
                current_phrase = self.chosen_affirmative_phrase
                event = self.interruptible_event_factory.create_interruptible_event(
                    payload=TranscriptionAgentInput(
                        transcription=transcription,
                        affirmative_phrase=current_phrase,
                        conversation_id=self.conversation.id,
                        vonage_uuid=getattr(self.conversation, "vonage_uuid", None),
                        twilio_sid=getattr(self.conversation, "twilio_sid", None),
                        ctx=self.conversation.conversation_span,
                    ),
                )

                # Get the latest bot and human messages
                latest_human_message = initial_buffer
                if (
                    isinstance(self.conversation.agent, StateAgent)
                    and latest_human_message.strip().lower() != "hello"
                ):
                    try:
                        latest_bot_message = (
                            self.conversation.agent.get_latest_bot_message()
                        )

                        # Prepare the request data
                        request_data = {
                            "question": latest_bot_message,
                            "response": latest_human_message,
                        }

                        # Make the async request
                        start_time = time.time()
                        async with httpx.AsyncClient() as client:
                            # the trailing slash is required, or we'll get stuck in a redirect loop
                            response = await client.post(
                                "http://endpoint-classifier-endpoint-classifier-svc.default.svc.cluster.local:58000/inference/",
                                headers={
                                    "accept": "application/json",
                                    "Content-Type": "application/json",
                                },
                                json=request_data,
                                timeout=0.5,
                                follow_redirects=True,
                            )
                        request_duration = time.time() - start_time

                        # Parse the response and calculate sleep time
                        if not isinstance(response, str):
                            response = response.text
                        # sleep_time = (float(response) ** 2) * 1.5 - request_duration
                        sleep_time = (
                            float(response) * float(response)
                        ) - request_duration
                        # if self.vad_detected:
                        #     sleep_time = sleep_time * 2
                        if sleep_time > 0:
                            # TODO: HERE, CONNECT IT TO THE SLIDER
                            self.conversation.logger.info(
                                f"heuristically sleeping for {sleep_time} seconds"
                            )
                            await asyncio.sleep(sleep_time)
                    except Exception as e:
                        self.conversation.logger.error(f"Error making request: {e}")

                    # Place the event in the output queue for further processing
                self.output_queue.put_nowait(event)
                self.conversation.mark_last_action_timestamp()
                self.conversation.allow_idle_message = True

                self.conversation.logger.info("Transcription event put in output queue")
                # release the action, if there is one
                self.conversation.agent.can_send = True
                self.buffer_check_task = None
                return
            except Exception as e:
                self.conversation.logger.error(f"Error in _buffer_check: {e}")

        async def process(self, transcription: Transcription):
            if self.first_message_lock:
                self.conversation.logger.debug(
                    "Ignoring transcription on initial message"
                )
                self.conversation.mark_last_action_timestamp()
                return
            if (
                self.conversation.agent.block_inputs
            ):  # the two block inputs are different
                self.conversation.logger.debug(
                    "Ignoring transcription since we are awaiting a tool call."
                )
                self.conversation.mark_last_action_timestamp()
                return
            # if self.block_inputs and not self.agent.agent_config.allow_interruptions:
            #     self.conversation.logger.debug(
            #         "Ignoring transcription since we are in-flight..."
            #     )
            #     return

            if (
                not self.agent.agent_config.allow_interruptions
                and self.conversation.is_agent_speaking()
            ):
                self.conversation.logger.debug(
                    "Ignoring transcription since we are SPEAKING..."
                )
                self.conversation.mark_last_action_timestamp()
                # clear the buffer
                return
            # If the message is just "vad", handle it without resetting the buffer check
            if transcription.message.strip() == "vad":

                self.vad_detected = True
                stashed_buffer = deepcopy(self.buffer)
                self.conversation.logger.info(f"Broadcasting interrupt from VAD")
                await self.conversation.broadcast_interrupt()
                if stashed_buffer and self.buffer:
                    if len(stashed_buffer) > 0 and len(self.buffer) > 0:
                        if stashed_buffer != self.buffer:
                            if self.buffer.to_message().startswith(
                                stashed_buffer.to_message()
                            ):
                                self.conversation.logger.info(
                                    f"Stashed buffer is a prefix of current buffer, using current buffer (vad)"
                                )
                            else:
                                self.conversation.logger.info(
                                    f"Stashed buffer is not a prefix of current buffer, concatenating (vad)"
                                )
                                self.buffer.update_buffer(stashed_buffer, True)
                    elif len(stashed_buffer) > 0:
                        self.conversation.logger.info(
                            f"Only stashed buffer has content, using stashed buffer (vad)"
                        )
                        self.buffer = stashed_buffer
                    elif len(self.buffer) > 0:
                        self.conversation.logger.info(
                            f"Only current buffer has content, keeping current buffer (vad)"
                        )
                    else:
                        self.conversation.logger.info(f"Both buffers are empty (vad)")
                        return
                self.conversation.transcriber.VOLUME_THRESHOLD = 700
                if self.buffer_check_task:
                    try:
                        self.conversation.logger.info("Cancelling buffer check task")
                        cancelled = self.buffer_check_task.cancel()
                        self.conversation.logger.info(f"BufferCancel? {cancelled}")
                        self.buffer_check_task = None
                    except Exception as e:
                        self.conversation.logger.error(
                            f"Error cancelling buffer check task: {e}"
                        )
                self.buffer_check_task = asyncio.create_task(
                    self._buffer_check(deepcopy(self.buffer.to_message()))
                )
                return
            else:
                self.vad_detected = False
            if "words" not in json.loads(transcription.message):
                self.conversation.logger.info(
                    "Ignoring transcription, no word content."
                )
                return
            elif len(json.loads(transcription.message)["words"]) == 0:
                # when we wait more, they were silent so we want to push out a filler audio
                # self.conversation.logger.info(
                #     "Ignoring transcription, zero words in words."
                # )
                return

            self.conversation.logger.debug(
                f"Transcription message: {' '.join(word['word'] for word in json.loads(transcription.message)['words'])}"
            )
            # Mark the timestamp of the last action
            self.conversation.mark_last_action_timestamp()

            # Reset the threshold for the next transcription
            self.conversation.transcriber.VOLUME_THRESHOLD = 700

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
            self.time_silent = 0.0
            # Update the buffer with the new message if it contains new content and log it
            new_words = json.loads(transcription.message)["words"]

            self.buffer.update_buffer(new_words, transcription.is_final)
            # we also want to update the last user message

            self.vad_time = 2.0
            self.time_silent = transcription.time_silent

            # If a buffer check task exists, cancel it and start a new one
            if self.buffer_check_task:
                try:
                    self.conversation.logger.info("Cancelling buffer check task")
                    cancelled = self.buffer_check_task.cancel()
                    self.conversation.logger.info(f"BufferCancel? {cancelled}")
                    self.buffer_check_task = None
                except Exception as e:
                    self.conversation.logger.error(
                        f"Error cancelling buffer check task: {e}"
                    )
            # if its not final, the rest of this function is skipped.
            # if not transcription.is_final:
            #     return
            if self.initial_message is not None:
                # Signal to start responding with first message.
                # Block further transcriptions
                # Let the first message function handle updating the first message and release lock.
                # This assumes that send_initial_message is uncancellable during the first 2 seconds of audio.
                # If there is any senario where first message is cancellable,
                # we will end up with invalid state and block all transcriptions.

                self.first_message_lock = True  # Lock first
                asyncio.create_task(
                    self.conversation.send_initial_message(self.initial_message)
                )  # Create task second
                return
            stashed_buffer = deepcopy(self.buffer)
            # Broadcast an interrupt and set the buffer status to DISCARD
            await self.conversation.broadcast_interrupt()
            if stashed_buffer != self.buffer:
                self.conversation.logger.info(
                    f"Buffer changed on interrupt, putting stashed buffer back"
                )
                self.buffer = stashed_buffer
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
            self.chunk_size = int(
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

                if isinstance(agent_response, AgentResponseGenerationComplete):
                    self.conversation.logger.debug("Agent response generation complete")
                    self.conversation.agent.mark_start = False
                    return
                agent_response_message = typing.cast(
                    AgentResponseMessage, agent_response
                )
                self.conversation.mark_last_action_timestamp()

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
                        f"SYNTH: Ignoring empty or non-letter agent response message: {agent_response_message.message.text}"
                    )
                    return
                # get the prompt preamble
                if isinstance(self.conversation.agent, CommandAgent) or isinstance(
                    self.conversation.agent, StateAgent
                ):

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
                        # if there is a starting double quote, and an odd number of double quotes, rmeove it
                        if translated_message.startswith('"'):
                            double_quote_count = translated_message.count('"')
                            if double_quote_count % 2 == 1:
                                translated_message = translated_message[1:]
                        agent_response_message.message.text = translated_message
                        synthesis_result = (
                            await self.conversation.synthesizer.create_speech(
                                agent_response_message.message,
                                self.chunk_size,
                                bot_sentiment=self.conversation.bot_sentiment,
                            )
                        )

                        agent_response_message.message.text = current_message
                    else:
                        agent_response_message.message.text = (
                            agent_response_message.message.text.strip()
                        )
                        # if there is a starting double quote, and an odd number of double quotes, rmeove it
                        if agent_response_message.message.text.startswith('"'):
                            double_quote_count = (
                                agent_response_message.message.text.count('"')
                            )
                            if double_quote_count % 2 == 1:
                                agent_response_message.message.text = (
                                    agent_response_message.message.text[1:]
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
                    # self.conversation.logger.info(
                    #     f"[{self.conversation.agent.agent_config.call_type}:{self.conversation.agent.agent_config.current_call_id}] Agent: {agent_response_message.message.text}"
                    # )
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
                    self.current_task = None
                except Exception as e:
                    # If an exception occurs, log it and set the message as cut off.
                    self.conversation.logger.debug(f"Detected Task cancelled: {e}")
                    message_sent, cut_off = "", True
                    self.current_task = None
                    return

                # Once the speech output is complete, publish the transcript message with the actual content spoken.
                transcript_message.text = transcript_message.text.replace("Err...", "")
                # split on < and truncate there
                transcript_message.text = transcript_message.text.split("<")[0].strip()
                # Don't publish the transcript message if it's an action starting phrase (always ends in ellipsis)
                if not transcript_message.text.strip().endswith("..."):
                    self.conversation.transcript.maybe_publish_transcript_event_from_message(
                        message=transcript_message,
                        conversation_id=self.conversation.id,
                    )
                # lets do the equivalent for state agent here
                # first check if the latest message is a bot message
                if (
                    len(self.conversation.agent.chat_history) > 0
                    and self.conversation.agent.chat_history[-1][0] == "message.bot"
                ):
                    self.conversation.agent.chat_history[-1] = (
                        "message.bot",
                        BaseMessage(
                            text=self.conversation.agent.chat_history[-1][1].text
                            + message_sent
                        ),
                    )
                else:
                    self.conversation.agent.chat_history.append(
                        ("message.bot", BaseMessage(text=message_sent))
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
                self.current_task = None
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
        self.conversation_span = tracer.start_span(f"conversation::{self.id}")
        self.logger.debug(f"Conversation ID: {self.id}")
        # threadingevent
        self.stop_event = threading.Event()
        self.interrupt_count = 0
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
        # This is used to track if the generate completion function has returned yet.
        # If it has not, we do not want send speech to output to unmute.
        self.allow_unmute: bool = True

        # tracing
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.logger.debug("Conversation created")
        self.allow_idle_message = False
        self.mark_start_speech = False

    def create_state_manager(self) -> ConversationStateManager:
        return ConversationStateManager(conversation=self)

    async def start(self, mark_ready: Optional[Callable[[], Awaitable[None]]] = None):
        self.logger.debug("Convo starting")

        self.transcriber.start()
        self.transcriptions_worker.start()
        initial_message = None
        if self.agent.get_agent_config().call_type == CallType.INBOUND:
            self.transcriber.mute()
            initial_message = self.agent.get_agent_config().initial_message
            self.transcriptions_worker.initial_message = initial_message
        else:
            initial_message = self.agent.get_agent_config().initial_message
            self.transcriptions_worker.initial_message = initial_message
            self.transcriber.unmute()  # take in audio immediately in outbound
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
        self.logger.debug("Agent starting")
        self.agent.start()
        self.logger.debug("Agent started")
        if isinstance(self.agent, CommandAgent) or isinstance(self.agent, StateAgent):
            self.agent.conversation_id = self.id
            self.agent.twilio_sid = getattr(self, "twilio_sid", None)
        call_type = self.agent.get_agent_config().call_type
        self.agent.attach_transcript(self.transcript)

        if initial_message is not None and call_type == CallType.INBOUND:
            self.logger.debug(f"Sending initial message: {initial_message}")
            asyncio.create_task(
                self.send_initial_message(initial_message)
            )  # TODO: this seems like its hanging, why not await?
            self.transcriptions_worker.initial_message = None

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
        initial_message_span = start_span_in_ctx(
            name="send_initial_message", parent_span=self.conversation_span
        )
        # TODO: configure if initial message is interruptible
        initial_message_tracker = asyncio.Event()
        if self.agent.get_agent_config().call_type == CallType.OUTBOUND:
            self.agent.update_history(
                "human", self.transcriptions_worker.buffer.to_message()
            )
        self.agent.update_history(
            "message.bot",
            initial_message.text,
            agent_response_tracker=initial_message_tracker,
        )
        # Start a timer to track when 2 seconds have passed
        start_time = time.time()
        self.transcriber.VOLUME_THRESHOLD = 8000  # make it so high vad wont interrupt it, only a real transcription will
        previous_allow_interruptions = self.agent.agent_config.allow_interruptions
        # only run the loop if we're in outbound mode
        if self.agent.get_agent_config().call_type == CallType.OUTBOUND:
            while not initial_message_tracker.is_set():
                await asyncio.sleep(0.05)  # Check every 0.1 seconds
                # self.logger.debug(f"Time elapsed: {time.time() - start_time}")
                if time.time() - start_time >= 2:
                    self.logger.debug("Releasing lock")
                    # 1. update initial message to none
                    # 2. release lock on transcriptions worker
                    self.transcriptions_worker.initial_message = None
                    self.transcriptions_worker.first_message_lock = False
                    self.transcriber.unmute()
                    self.transcriptions_worker.block_inputs = False
                    self.agent.agent_config.allow_interruptions = True
                    # span_event(
                    #     span=initial_message_span,
                    #     event_name="release-lock",
                    #     event_data={"time": time.time() - start_time},
                    # )
                    break
        if not initial_message_tracker.is_set():
            await initial_message_tracker.wait()
        # span_event(
        #     span=initial_message_span,
        #     event_name="message_sent",
        #     event_data={"time": time.time() - start_time},
        # )
        # The initial message can be sent in under 2 seconds so update again
        self.transcriptions_worker.initial_message = None
        self.transcriptions_worker.first_message_lock = False
        self.transcriber.VOLUME_THRESHOLD = 700  # turn it back down
        self.agent.agent_config.allow_interruptions = previous_allow_interruptions
        end_span(initial_message_span)

    async def check_for_idle(self):
        """Terminates the conversation after 15 seconds if no activity is detected"""
        idle_prompt_sent = False
        while self.is_active():
            if (
                time.time() - self.last_action_timestamp > 8
                and not idle_prompt_sent
                and self.allow_idle_message
                and self.transcriptions_worker.initial_message is None
                and not self.is_agent_speaking()
            ):
                idle_prompt_sent = True
                idle_prompt_message_tracker = asyncio.Event()
                message_options = [
                    "Just let me know when you're ready.",
                    "No rush at all, take your time.",
                    "I'm still here when you're ready to continue.",
                    "Let me know when you're ready to continue.",
                    "I'm all ears whenever you're ready.",
                    "Feel free to take a moment if you need it.",
                    "Whenever you're ready to proceed, just say the word.",
                ]
                to_send = BaseMessage(text=random.choice(message_options))
                agent_response_event = self.interruptible_event_factory.create_interruptible_agent_response_event(
                    AgentResponseMessage(message=to_send),
                    is_interruptible=False,
                    agent_response_tracker=idle_prompt_message_tracker,
                )
                self.agent_responses_worker.consume_nonblocking(agent_response_event)
                self.allow_idle_message = False
                self.agent.block_inputs = False
            if (
                time.time() - self.last_action_timestamp > 4
                and time.time() - self.last_action_timestamp < 30
            ):
                # if more than 4 seconds of idle time there is possible bg noise
                # and we want to decrease the sensitivity of vad
                self.transcriber.VOLUME_THRESHOLD = 5000
            else:
                self.transcriber.VOLUME_THRESHOLD = 700
                idle_prompt_sent = False
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

    def is_agent_speaking(self) -> bool:
        """
        Checks if the agent is currently speaking.
        """

        return (
            (
                self.synthesis_results_worker.current_task is not None
                and not self.synthesis_results_worker.current_task.done()
            )
            or (self.agent_responses_worker.output_queue.qsize() > 0)
            or (self.synthesis_results_queue.qsize() > 0)
            or (self.output_device.queue.qsize() > 0)
            or (self.mark_start_speech)
        )

    async def broadcast_interrupt(self):
        """Stops all inflight events and cancels all workers that are sending output

        Returns true if any events were interrupted - which is used as a flag for the agent (is_interrupt)
        """
        self.agent.cancel_stream()
        self.logger.debug("Broadcasting interrupt")
        self.stop_event.set()
        self.mark_last_action_timestamp()
        if isinstance(self.agent, CommandAgent):
            self.agent.stop = not self.agent.stop
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
        await self.output_device.clear()
        if not self.agent.get_agent_config().allow_interruptions:
            self.synthesis_results_worker.clear_task_queue()
        while True:
            try:
                interruptible_event = self.synthesis_results_queue.get_nowait()
                if not interruptible_event.is_interrupted():
                    if interruptible_event.interrupt():
                        self.logger.debug(" Synthesis Results Queue Interrupt Event")
                        num_interrupts += 1
            except asyncio.QueueEmpty:
                break
        self.allow_unmute = True
        self.agent.block_inputs = False
        self.transcriptions_worker.block_inputs = False
        self.agent.mark_start = False
        self.mark_start_speech = False
        await self.output_device.clear()
        self.logger.debug(
            f"Finished broadcasting interrupt, num_interrupts: {num_interrupts}"
        )
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
        if not (synthesis_result and message):
            return "", False
        stop_event.clear()

        self.transcriptions_worker.synthesis_done = False
        message_sent = message
        cut_off = False

        chunk_size = seconds_per_chunk * get_chunk_size_per_second(
            self.synthesizer.get_synthesizer_config().audio_encoding,
            self.synthesizer.get_synthesizer_config().sampling_rate,
        )
        if self.agent.mark_start:
            self.mark_start_speech = True

        speech_data = bytearray()
        held_buffer = self.transcriptions_worker.buffer.to_message()
        time_started_speaking = time.time()
        buffer_cleared = False
        total_time_sent = 0
        moved_back = False
        async for chunk_result in synthesis_result.chunk_generator:

            if stop_event.is_set() and self.agent.agent_config.allow_interruptions:
                return "", False

            speech_data.extend(chunk_result.chunk)

            if len(speech_data) > chunk_size:
                self.transcriptions_worker.block_inputs = True
                self.transcriptions_worker.time_silent = 0.0
                self.transcriptions_worker.triggered_affirmative = False
                # self.logger.debug(f"Sending chunk, len {len(speech_data)}")

                if self.agent.agent_config.allow_interruptions:
                    self.mark_last_action_timestamp()

                    if stop_event.is_set():
                        # self.agent.move_back_state()
                        self.logger.debug(
                            "Moved back state from send_speech_to_output in the middle"
                        )
                        moved_back = True
                        return "", False

                await self.output_device.consume_nonblocking(speech_data)
                chunk_time = len(speech_data) / (chunk_size / seconds_per_chunk)
                total_time_sent += chunk_time

                speech_data = bytearray()

        if not stop_event.is_set():
            self.logger.debug(f"Sending final chunk, len {len(speech_data)}")
            await self.output_device.consume_nonblocking(speech_data)
            self.transcriptions_worker.time_silent = 0.0
            total_time_sent += len(speech_data) / (chunk_size / seconds_per_chunk)
        else:
            self.logger.debug("Interrupted speech output on the last chunk")
            # if not moved_back:
            #     self.agent.move_back_state()
            return "", False

        self.transcriptions_worker.synthesis_done = True

        if self.transcriptions_worker.buffer_check_task:
            self.logger.debug(
                "Buffer check task found, interrupting from send_speech_to_output"
            )
            return "", False
        else:
            self.logger.debug("No buffer check task found, proceeding.")

        self.transcriptions_worker.block_inputs = True
        self.transcriptions_worker.time_silent = 0.0
        self.transcriptions_worker.triggered_affirmative = False

        self.logger.info(f"Total speech time: {total_time_sent} seconds")

        self.mark_last_action_timestamp()
        # This will be changed when the partial synthesis is added.
        # Doesn't really matter for now but 2 seconds it too long.
        # Added stop event check otherwise it will block other synthesis result tasks
        # even though we meant to cancel this one.
        sleep_interval = 0.1  # Mark last action every 0.1 seconds
        remaining_sleep = total_time_sent
        while remaining_sleep > 0:
            await asyncio.sleep(min(sleep_interval, remaining_sleep))
            if stop_event.is_set():
                self.logger.debug("Interrupted speech output on the last chunk")
                # self.agent.move_back_state()
                return "", False
            self.mark_last_action_timestamp()
            remaining_sleep -= sleep_interval
        # This ensures we do volume thresholding and mark last action periodically
        message_sent = synthesis_result.get_message_up_to(total_time_sent)
        replacer = "\n"
        if not stop_event.is_set():
            self.logger.info(
                f"[CallType.{self.agent.agent_config.call_type.upper()}:{self.agent.agent_config.current_call_id}] Agent: {message_sent.replace(replacer, ' ')}"
            )
        if transcript_message:
            transcript_message.text = message_sent
        cut_off = False
        if self.mark_start_speech:
            self.mark_start_speech = False
            self.logger.info("Marked start speech")

        self.transcriptions_worker.synthesis_done = False

        if not stop_event.is_set() and not buffer_cleared:
            buffer_cleared = True
            self.transcriptions_worker.synthesis_done = True
            started_event.set()
            self.transcriber.VOLUME_THRESHOLD = 1000
            self.transcriptions_worker.buffer.clear()  # only clear it once sent
            self.logger.debug("Cleared buffer from send_speech_to_output")

            # self.agent.restore_resume_state()

        if message_sent:
            self.logger.info(f"Responding to {held_buffer}")
            if self.allow_unmute:
                self.transcriptions_worker.block_inputs = False
                if self.transcriber.get_transcriber_config().mute_during_speech:
                    self.logger.debug("Unmuting transcriber")
                    self.transcriber.unmute()
        self.transcriptions_worker.ready_to_send = BufferStatus.DISCARD

        return message_sent, cut_off

    def mark_terminated(self):
        self.active = False

    async def terminate(self):
        self.mark_terminated()
        end_span(self.conversation_span)
        await self.broadcast_interrupt()
        self.output_device.terminate()

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
            isinstance(self.agent, CommandAgent) or isinstance(self.agent, StateAgent)
        ) and self.agent.agent_config.vector_db_config:
            # Shutting down the vector db should be done in the agent's terminate method,
            # but it is done here because `vector_db.tear_down()` is async and
            # `agent.terminate()` is not async.
            self.logger.debug("Terminating vector db")
            self.agent.streamed = False
            await self.agent.vector_db.tear_down()
        self.agent.terminate()
        self.logger.debug("Terminating output device")
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
