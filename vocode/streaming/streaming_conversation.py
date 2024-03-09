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
from vocode import getenv
from openai import AsyncOpenAI, OpenAI


from vocode.streaming.action.worker import ActionsWorker

from vocode.streaming.agent.bot_sentiment_analyser import (
    BotSentimentAnalyser,
)
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
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

from vocode.streaming.models.agent import ChatGPTAgentConfig, FillerAudioConfig
from vocode.streaming.models.synthesizer import (
    SentimentConfig,
)

from vocode.streaming.agent.utils import (
    format_openai_chat_messages_from_transcript,
    collate_response_async,
    openai_get_tokens,
    vector_db_result_to_openai_chat_message,
    format_openai_chat_completion_from_transcript,
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

        def _update_or_add_word(self, new_word):
            overlap_indices = []

            for i, existing_word in enumerate(self.buffer):
                if self._is_overlap(new_word, existing_word):
                    overlap_indices.append(i)

            if not overlap_indices:
                self.buffer.append(new_word)
            else:
                for i in sorted(overlap_indices, reverse=True):
                    del self.buffer[i]
                self.buffer.append(new_word)

            self.buffer.sort(key=lambda x: x["start"])

        def _is_overlap(self, word1, word2, tolerance=0.05):
            # Adjust the start and end times of the words by a tolerance to account for slight shifts
            adjusted_word1_start = word1["start"] - tolerance
            adjusted_word1_end = word1["end"] + tolerance
            adjusted_word2_start = word2["start"] - tolerance
            adjusted_word2_end = word2["end"] + tolerance

            # Check for overlap with adjusted timings
            return not (
                adjusted_word1_end <= adjusted_word2_start
                or adjusted_word1_start >= adjusted_word2_end
            )

        def _merge_and_clean_buffer(self):
            merged_buffer = []
            for word in self.buffer:
                if not merged_buffer:
                    merged_buffer.append(word)
                else:
                    last_word = merged_buffer[-1]
                    if not self._is_overlap(word, last_word):
                        merged_buffer.append(word)
                    else:
                        # If the words overlap, merge them
                        if word["end"] > last_word["end"]:
                            last_word["end"] = word["end"]
                        if "confidence" in word and "confidence" in last_word:
                            # Take the maximum confidence of the overlapping words
                            last_word["confidence"] = max(
                                last_word["confidence"], word["confidence"]
                            )
                        # If the words are the same, keep the one with higher confidence
                        elif word["word"] == last_word["word"]:
                            if word.get("confidence", 0) > last_word.get(
                                "confidence", 0
                            ):
                                merged_buffer[-1] = word
            self.buffer = merged_buffer

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
            # removed the buffer_utterances
            # self.num_buffer_utterances = 0
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

        async def get_expected_silence_duration(self, buffer: str) -> float:
            previous_agent_message = next(
                (
                    message["content"]
                    for message in reversed(
                        format_openai_chat_messages_from_transcript(
                            self.conversation.transcript
                        )
                    )
                    if message["role"] == "assistant"
                    and message["content"].strip() != ""
                ),
                "The conversation has just started. There are no previous agent messages.",
            )

            # Define a constant for max silence time
            MAX_SILENCE_TIME = MAX_SILENCE_DURATION

            # Prepare the data for the POST request
            data = {
                "question": previous_agent_message,
                "response": buffer,
            }

            # Prepare headers for the POST request
            headers = {
                "Content-Type": "application/json",
            }
            self.conversation.logger.debug(
                f"Sending classification request with data: {data}"
            )
            # Perform the POST request to classify the dialogue asynchronously
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://148.64.105.83:58000/inference/", headers=headers, json=data
                ) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        classification = response_data["classification"]
                        confidence = response_data["confidence"]

                        # Handle the classification cases and calculate expected silence duration
                        if classification == "paused":
                            # In the paused case, we do the filler word and wait based on confidence
                            expected_silence_duration = confidence * MAX_SILENCE_TIME
                            self.last_classification = "paused"
                            self.conversation.logger.debug(
                                f"Classification: {classification}, Confidence: {confidence}, Expected silence: {expected_silence_duration}"
                            )
                            return expected_silence_duration
                        elif classification == "truncated":
                            # In the truncated case, we say no filler word and we wait on confidence
                            expected_silence_duration = confidence * MAX_SILENCE_TIME
                            self.last_classification = "truncated"
                            self.conversation.logger.debug(
                                f"Classification: {classification}, Confidence: {confidence}, Expected silence: {expected_silence_duration}"
                            )
                            return expected_silence_duration
                        elif classification == "full":
                            self.conversation.logger.error(
                                f"Full classification received: {classification}"
                            )
                            # invert confidence
                            expected_silence_duration = (
                                1 - confidence
                            ) * MAX_SILENCE_TIME
                            self.last_classification = "full"
                            self.conversation.logger.debug(
                                f"Classification: {classification}, Confidence: {confidence}, Expected silence: {expected_silence_duration}"
                            )
                            return expected_silence_duration
                        else:
                            self.conversation.logger.error(
                                f"Unexpected classification received: {classification}"
                            )
                            return 0.0
                    else:
                        self.conversation.logger.error(
                            f"Failed to get classification, status code: {response.status}"
                        )
                        return 0.0

        async def _buffer_check(self, initial_buffer):
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
            # Calculate the expected silence duration after the current buffer
            start_expected_duration = time.time()
            expected_silence_duration = (
                await self.get_expected_silence_duration(initial_buffer)
                - self.time_silent
            )
            elapsed_time_duration = time.time() - start_expected_duration
            expected_silence_duration -= elapsed_time_duration

            # Ensure the sleep time is at least 0.1 seconds
            self.current_sleep_time = max(expected_silence_duration, 0.5)

            # Log the time taken for classification and the calculated sleep duration
            self.conversation.logger.info(
                f"Classification took: {elapsed_time_duration}\nSleep duration: {self.current_sleep_time}"
            )

            # choose a random affirmative phrase until it's different from the previous one
            previous_phrase = self.chosen_affirmative_phrase
            while True:
                self.chosen_affirmative_phrase = random.choice(
                    self.conversation.synthesizer.affirmative_audios
                ).message.text
                if self.chosen_affirmative_phrase != previous_phrase:
                    break
            # Create an interruptible event with the transcription data
            current_phrase = self.chosen_affirmative_phrase
            if self.conversation.agent.agent_config.pending_action == "pending":
                current_phrase = "I see."
                # make the transcription tell the agent to wait
                transcription = Transcription(
                    message="SYSTEM: There is a pending request still.\nUser: "
                    + transcription.message,
                    confidence=1.0,  # We assume full confidence as it's not explicitly provided
                    is_final=True,
                    time_silent=self.time_silent,
                )
            event = self.interruptible_event_factory.create_interruptible_event(
                payload=TranscriptionAgentInput(
                    transcription=transcription,
                    affirmative_phrase=current_phrase,
                    conversation_id=self.conversation.id,
                    vonage_uuid=getattr(self.conversation, "vonage_uuid", None),
                    twilio_sid=getattr(self.conversation, "twilio_sid", None),
                ),
            )

            sleeping_time = self.current_sleep_time

            # Place the event in the output queue for further processing
            self.output_queue.put_nowait(event)

            self.conversation.logger.info("Transcription event put in output queue")

            # Set the buffer status to HOLD, indicating we're not ready to send it yet
            self.ready_to_send = BufferStatus.HOLD

            # HERE, we will send of the affirmative audio if the sleeping time > 1.5 and the time since last filler is > 3

            log_interval = 1.0  # Log at most every 1 second
            time_since_last_log = 0.0
            while sleeping_time > 0.01:
                sleeping_time = self.current_sleep_time
                self.sleeping_time = min(1.5, sleeping_time)
                if self.last_classification == "paused":
                    if (
                        time.time() - self.last_filler_time > 4
                        and time.time() - self.last_affirmative_time > 2
                        and len(self.buffer.to_message().strip().split()) > 3
                    ):
                        self.conversation.agent_responses_worker.send_filler_audio(
                            asyncio.Event()
                        )
                        self.last_filler_time = time.time()
                if (
                    sleeping_time > 0.5
                    and time.time() - self.last_filler_time > 2
                    and len(initial_buffer.strip().split()) > 3
                    and time.time() - self.last_affirmative_time > 3
                    and not self.triggered_affirmative
                    and self.last_classification == "full"
                ) or (
                    self.time_silent > 0.7
                    and not self.triggered_affirmative
                    and time.time() - self.last_filler_time > 1.5
                    and time.time() - self.last_affirmative_time > 3
                    and not self.last_classification == "paused"
                ):
                    self.triggered_affirmative = True

                    self.conversation.logger.info(
                        f"Sending affirmative audio, sleeping time: {self.current_sleep_time}"
                    )
                    self.conversation.agent_responses_worker.send_affirmative_audio(
                        # self.interruptible_event_factory.create_interruptible_event(
                        #     payload=None
                        # )
                        asyncio.Event(),
                        phrase=self.chosen_affirmative_phrase,
                    )
                    self.last_affirmative_time = time.time()
                if not self.synthesis_done and self.current_sleep_time < 0.02:

                    self.conversation.logger.debug(
                        f"Added sleep for synthesis to finish..."
                    )
                    self.current_sleep_time = 0.02
                    if (
                        not self.triggered_affirmative
                        and time.time() - self.last_filler_time > 1.0
                        and time.time() - self.last_affirmative_time > 2.0
                        # and self.last_classification == "full"
                    ):
                        self.triggered_affirmative = True
                        self.conversation.agent_responses_worker.send_affirmative_audio(
                            asyncio.Event(),
                            phrase=self.chosen_affirmative_phrase,
                        )
                        self.last_affirmative_time = time.time()

                await asyncio.sleep(0.01)
                if self.current_sleep_time > 0:
                    self.current_sleep_time -= 0.01
                time_since_last_log += 0.01
                if time_since_last_log >= log_interval:
                    self.conversation.logger.info(
                        f"Sleeping... {self.current_sleep_time} seconds left"
                    )
                    time_since_last_log = 0.0
                if self.synthesis_done:
                    # self.conversation.logger.info("Synthesis done, still sleeping")
                    if (
                        time.time() - self.last_filler_time > 1.0
                        and time.time() - self.last_affirmative_time > 2.0
                        and self.time_silent > 0.5
                        # and not self.last_classification == "paused"
                    ):
                        self.triggered_affirmative = True
                        self.last_affirmative_time = time.time()

                        # self.conversation.logger.info(
                        #     f"Sending affirmative audio, sleeping time: {self.current_sleep_time}"
                        # )
                        self.conversation.agent_responses_worker.send_affirmative_audio(
                            # self.interruptible_event_factory.create_interruptible_event(
                            #     payload=None
                            # )
                            asyncio.Event(),
                            phrase=self.chosen_affirmative_phrase,
                        )
                        self.last_affirmative_time = time.time()

            self.conversation.logger.info(f"Marking as send")
            self.ready_to_send = BufferStatus.SEND

        async def process(self, transcription: Transcription):
            # Ignore the transcription if we are currently in-flight (i.e., the agent is speaking)
            # log the current transcript

            if self.block_inputs:
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
                    # self.current_sleep_time = min(
                    #     2,
                    #     max(
                    #         self.vad_time,
                    #         min(
                    #             self.current_sleep_time * 1.5,
                    #             self.current_sleep_time + 2,
                    #         ),
                    #     ),
                    # )
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
            # if len(new_words) != len(self.buffer.get_buffer()):
            #     self.conversation.logger.info(
            #         f"changed, old: {len(self.buffer.get_buffer())}"
            #     )
            #     self.buffer.update_buffer(new_words)
            #     self.conversation.logger.info(len(f"changed, new: {new_words}"))
            # else:
            #     self.conversation.logger.info(
            #         f"buffer was not changed: {self.buffer.to_message()}"
            #     )
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
                # silence_threshold = (
                #     self.conversation.filler_audio_config.silence_threshold_seconds
                # )
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
            assert self.conversation.filler_audio_worker is not None
            self.conversation.logger.debug("Sending filler audio")
            if self.conversation.synthesizer.filler_audios:
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
            assert self.conversation.filler_audio_worker is not None
            self.conversation.logger.debug("Sending affirmative audio")
            if self.conversation.synthesizer.affirmative_audios:
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
                    char.isalpha() for char in agent_response_message.message.text
                ):
                    self.conversation.logger.debug(
                        "SYNTH: Ignoring empty or non-letter agent response message"
                    )
                    return
                synthesis_result = await self.conversation.synthesizer.create_speech(
                    agent_response_message.message,
                    self.chunk_size,
                    bot_sentiment=self.conversation.bot_sentiment,
                )
                self.convoCache[str(agent_response_message.message)] = synthesis_result
                self.produce_interruptible_agent_response_event_nonblocking(
                    (agent_response_message.message, synthesis_result),
                    is_interruptible=item.is_interruptible,
                    agent_response_tracker=item.agent_response_tracker,
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
                    item.interruption_event,
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

                # If the message was cut off, update the last bot message accordingly.
                if cut_off:
                    self.conversation.agent.update_last_bot_message_on_cut_off(
                        message_sent
                    )

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
        if self.agent.get_agent_config().send_filler_audio:
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
        self.transcriber.mute()
        # mute at the start
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

        if self.agent.get_agent_config().send_filler_audio:
            if not isinstance(
                self.agent.get_agent_config().send_filler_audio, FillerAudioConfig
            ):
                self.filler_audio_config = FillerAudioConfig()
            else:
                self.filler_audio_config = typing.cast(
                    FillerAudioConfig, self.agent.get_agent_config().send_filler_audio
                )
            filler_audio_task = asyncio.create_task(
                self.synthesizer.set_filler_audios(self.filler_audio_config)
            )
            affirmative_audio_task = asyncio.create_task(
                self.synthesizer.set_affirmative_audios(self.filler_audio_config)
            )
            prompt_preamble = self.agent.get_agent_config().prompt_preamble
            self.logger.debug(f"Prompt Preamble: {prompt_preamble}")

            await asyncio.gather(filler_audio_task, affirmative_audio_task)

        self.agent.start()
        initial_message = self.agent.get_agent_config().initial_message
        if initial_message:
            asyncio.create_task(self.send_initial_message(initial_message))
        else:
            # unmute if no initial message so they can speak first
            self.transcriber.unmute()
        self.agent.attach_transcript(self.transcript)
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
            if time.time() - self.last_action_timestamp > (
                self.agent.get_agent_config().allowed_idle_time_seconds
                or ALLOWED_IDLE_TIME
            ):
                self.logger.debug("Conversation idle for too long, terminating")
                await self.terminate()
                return
            await asyncio.sleep(15)

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
        if self.transcriptions_worker.block_inputs:
            # self.transcriptions_worker.is_final = False
            # self.transcriptions_worker.buffer = ""
            # self.transcriptions_worker.time_silent = 0.0
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
        seconds_per_chunk: int,
        transcript_message: Optional[Message] = None,
        started_event: Optional[threading.Event] = None,
    ):
        # Check if both the synthesis result and message are available, if not, return empty message and False flag
        if not (synthesis_result and message):
            return "", False

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

        # Asynchronously generate speech data from the synthesis result
        async for chunk_result in synthesis_result.chunk_generator:
            speech_data.extend(chunk_result.chunk)

        # Mark synthesis as done once all chunks are generated
        self.transcriptions_worker.synthesis_done = True

        # If no speech data is generated, return empty message and False flag
        if len(speech_data) == 0:
            return "", False

        # If a buffer check task exists, wait for it to complete before proceeding
        if self.transcriptions_worker.buffer_check_task:
            try:
                await self.transcriptions_worker.buffer_check_task
                # Handle cancellation of the buffer check task
                if self.transcriptions_worker.buffer_check_task.cancelled():
                    self.logger.debug("Buffer check task was cancelled.")
                    return "", False
                # # Handle non-send status after buffer check completion
                # elif self.transcriptions_worker.ready_to_send != BufferStatus.SEND:
                #     self.logger.debug(
                #         "Buffer check completed but buffer status is not SEND."
                #     )
                #     return "", False
            except asyncio.CancelledError:
                # Handle external cancellation of the buffer check task
                self.logger.debug(
                    "Buffer check task was cancelled by an external event."
                )
                return "", False
        else:
            # Proceed if no buffer check task is found
            self.logger.debug("No buffer check task found, proceeding without waiting.")

        held_buffer = self.transcriptions_worker.buffer.to_message()

        # Log the start of sending synthesized speech to the output device
        self.logger.debug("Sending in synth buffer")
        # Clear the transcription worker's buffer and related attributes before sending
        self.transcriptions_worker.block_inputs = True
        self.transcriptions_worker.time_silent = 0.0
        self.transcriptions_worker.triggered_affirmative = False
        self.transcriptions_worker.buffer.clear()

        # Send the generated speech data to the output device
        start_time = time.time()
        self.output_device.consume_nonblocking(speech_data)
        end_time = time.time()

        # Calculate the length of the speech in seconds
        speech_length_seconds = len(speech_data) / chunk_size
        if held_buffer and len(held_buffer) > 0:
            self.logger.info(
                f"[{self.agent.agent_config.call_type}:{self.agent.agent_config.current_call_id}] Lead:{held_buffer}"
            )
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
        # If a transcript message is provided, check if there is a pending action to execute
        if transcript_message and isinstance(self.agent, ChatGPTAgent):
            self.logger.info(
                f"The pending action is {self.agent.agent_config.pending_action}"
                f" and the current transcript text is {transcript_message.text}"
            )
            # If a pending action exists, execute it and reset the pending action
            if (
                self.agent.agent_config.pending_action
                and self.agent.agent_config.pending_action != "pending"
            ):
                asyncio.create_task(
                    self.agent.call_function(
                        self.agent.agent_config.pending_action,
                        TranscriptionAgentInput(
                            transcription=Transcription(
                                message=last_agent_message,
                                confidence=1.0,
                                is_final=True,
                                time_silent=0.0,
                            ),
                            conversation_id=self.id,
                            vonage_uuid=getattr(self, "vonage_uuid", None),
                            twilio_sid=getattr(self, "twilio_sid", None),
                        ),
                    )
                )
                # artificially submit a transcription for the bot to self respond saying that a request has been submitted
                transcription = Transcription(
                    message="SYSTEM: Pending: Your request has been submitted. No response yet.",
                    confidence=1.0,
                    is_final=True,
                )
                # # artificially submit a transcription for the bot to self respond
                # event = self.interruptible_event_factory.create_interruptible_event(
                #     payload=TranscriptionAgentInput(
                #         transcription=transcription,
                #         affirmative_phrase=self.chosen_affirmative_phrase,
                #         conversation_id=self.conversation.id,
                #         vonage_uuid=getattr(self.conversation, "vonage_uuid", None),
                #         twilio_sid=getattr(self.conversation, "twilio_sid", None),
                #     ),
                # )

                # # Place the event in the output queue for further processing
                # self.transcriptions_worker.output_queue.put_nowait(event)

                self.agent.agent_config.pending_action = "pending"

        # Sleep for the duration of the speech minus the time already spent sending the data
        sleep_time = max(
            speech_length_seconds
            - (end_time - start_time)
            - self.per_chunk_allowance_seconds,
            0,
        )
        if message_sent and len(message_sent.strip()) > 0:
            self.logger.info(
                f"[{self.agent.agent_config.call_type}:{self.agent.agent_config.current_call_id}] Agent: {message_sent}"
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
            isinstance(self.agent, ChatGPTAgent)
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
