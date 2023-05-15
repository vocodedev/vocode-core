import asyncio
import queue
import random
import threading
from typing import Any, Awaitable, Callable, Optional, Tuple
import logging
import time

from opentelemetry import trace
from opentelemetry.trace import Span

from vocode.streaming.agent.bot_sentiment_analyser import (
    BotSentimentAnalyser,
)
from vocode.streaming.models.events import TranscriptCompleteEvent
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.utils.events_manager import EventsManager
from vocode.streaming.utils.goodbye_model import GoodbyeModel
from vocode.streaming.utils.transcript import Transcript

from vocode.streaming.models.agent import (
    FillerAudioConfig,
    FILLER_AUDIO_DEFAULT_SILENCE_THRESHOLD_SECONDS,
)
from vocode.streaming.models.synthesizer import (
    SentimentConfig,
)
from vocode.streaming.constants import (
    TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS,
    PER_CHUNK_ALLOWANCE_SECONDS,
    ALLOWED_IDLE_TIME,
)
from vocode.streaming.agent.base_agent import BaseAgent
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
from vocode.streaming.utils.worker import (
    AsyncQueueWorker,
    InterruptibleEvent,
    InterruptibleWorker,
)

tracer = trace.get_tracer(__name__)
SYNTHESIS_TRACE_NAME = "synthesis"
AGENT_TRACE_NAME = "agent"

# TODO(ajay)
# - fix filler audio flow
# - fix goodbye flow


class StreamingConversation:
    class TranscriptionsWorker(AsyncQueueWorker):
        def __init__(
            self,
            input_queue: asyncio.Queue[Transcription],
            output_queue: asyncio.Queue[InterruptibleEvent[Transcription]],
            conversation: "StreamingConversation",
        ):
            super().__init__(input_queue, output_queue)
            self.input_queue = input_queue
            self.output_queue = output_queue
            self.conversation = conversation

        async def process(self, transcription: Transcription):
            self.conversation.mark_last_action_timestamp()
            if transcription.is_final:
                self.conversation.logger.debug(
                    "Got transcription: {}, confidence: {}".format(
                        transcription.message, transcription.confidence
                    )
                )
            if not self.conversation.is_human_speaking and transcription.confidence > (
                self.conversation.transcriber.get_transcriber_config().min_interrupt_confidence
                or 0
            ):
                self.conversation.current_transcription_is_interrupt = (
                    self.conversation.broadcast_interrupt()
                )
                if self.conversation.current_transcription_is_interrupt:
                    self.conversation.logger.debug("sending interrupt")
                self.conversation.logger.debug("Human started speaking")

            transcription.is_interrupt = (
                self.conversation.current_transcription_is_interrupt
            )
            self.conversation.is_human_speaking = not transcription.is_final
            if transcription.is_final:
                event = self.conversation.enqueue_interruptible_event(
                    payload=transcription
                )
                self.output_queue.put_nowait(event)

    class FinalTranscriptionsWorker(InterruptibleWorker):
        def __init__(
            self,
            input_queue: asyncio.Queue[InterruptibleEvent[Transcription]],
            output_queue: asyncio.Queue[InterruptibleEvent[Tuple[BaseMessage, bool]]],
            conversation: "StreamingConversation",
        ):
            super().__init__(input_queue, output_queue)
            self.input_queue = input_queue
            self.output_queue = output_queue
            self.conversation = conversation

        def send_filler_audio(self):
            self.conversation.logger.debug("Sending filler audio")
            if self.conversation.synthesizer.filler_audios:
                filler_audio = random.choice(
                    self.conversation.synthesizer.filler_audios
                )
                self.conversation.logger.debug(f"Chose {filler_audio.message.text}")
                event = self.conversation.enqueue_interruptible_event(
                    payload=filler_audio,
                    is_interruptible=filler_audio.is_interruptible,
                )
                self.conversation.filler_audio_worker.send_nonblocking(event)
            else:
                self.conversation.logger.debug(
                    "No filler audio available for synthesizer"
                )

        async def generate_responses(self, transcription: Transcription) -> bool:
            agent_span = tracer.start_span(
                AGENT_TRACE_NAME, {"generate_response": True}
            )
            responses = self.conversation.agent.generate_response(
                transcription.message,
                is_interrupt=transcription.is_interrupt,
                conversation_id=self.conversation.id,
            )
            should_wait_for_filler_audio = (
                self.conversation.agent.get_agent_config().send_filler_audio
            )
            is_first_response = True
            async for response in responses:
                if is_first_response:
                    agent_span.end()
                    if self.conversation.agent.get_agent_config().send_filler_audio:
                        self.conversation.filler_audio_worker.interrupt_current_filler_audio()
                        await self.conversation.filler_audio_worker.wait_for_filler_audio_to_finish()
                    is_first_response = False
                # TODO should this be in a different worker?
                if should_wait_for_filler_audio:
                    self.conversation.filler_audio_worker.interrupt_current_filler_audio()
                    await self.conversation.filler_audio_worker.wait_for_filler_audio_to_finish()
                    should_wait_for_filler_audio = False
                event = self.conversation.enqueue_interruptible_event(
                    payload=BaseMessage(text=response),
                    is_interruptible=self.conversation.agent.get_agent_config().allow_agent_to_be_cut_off,
                )
                self.output_queue.put_nowait(event)
            # TODO: implement should_stop for generate_responses
            return False

        async def respond(self, transcription: Transcription) -> bool:
            try:
                with tracer.start_span(AGENT_TRACE_NAME, {"generate_response": False}):
                    response, should_stop = await self.conversation.agent.respond(
                        transcription.message,
                        is_interrupt=transcription.is_interrupt,
                        conversation_id=self.conversation.id,
                    )
            except Exception as e:
                self.conversation.logger.error(
                    f"Error while generating response: {e}", exc_info=True
                )
                response = None
                return True
            # TODO should this be in a different worker?
            if self.conversation.agent.get_agent_config().send_filler_audio:
                self.conversation.filler_audio_worker.interrupt_current_filler_audio()
                await self.conversation.filler_audio_worker.wait_for_filler_audio_to_finish()
            if should_stop:
                return True
            if response:
                event = self.conversation.enqueue_interruptible_event(
                    payload=BaseMessage(text=response),
                    is_interruptible=self.conversation.agent.get_agent_config().allow_agent_to_be_cut_off,
                )
                self.output_queue.put_nowait(event)
            else:
                self.conversation.logger.debug("No response generated")
            return False

        async def process(self, item: InterruptibleEvent[Transcription]):
            try:
                transcription = item.payload
                self.conversation.transcript.add_human_message(
                    text=transcription.message,
                    events_manager=self.conversation.events_manager,
                    conversation_id=self.conversation.id,
                )
                goodbye_detected_task = None
                if (
                    self.conversation.agent.get_agent_config().end_conversation_on_goodbye
                ):
                    goodbye_detected_task = asyncio.create_task(
                        self.conversation.goodbye_model.is_goodbye(
                            transcription.message
                        )
                    )
                if self.conversation.agent.get_agent_config().send_filler_audio:
                    self.send_filler_audio()
                self.conversation.logger.debug("Responding to transcription")
                should_stop = False
                if self.conversation.agent.get_agent_config().generate_responses:
                    should_stop = await self.generate_responses(transcription)
                else:
                    should_stop = await self.respond(transcription)
                if should_stop:
                    self.conversation.logger.debug("Agent requested to stop")
                    self.conversation.mark_terminated()
                    return
                if goodbye_detected_task:
                    try:
                        goodbye_detected = await asyncio.wait_for(
                            goodbye_detected_task, 0.1
                        )
                        if goodbye_detected:
                            self.conversation.logger.debug(
                                "Goodbye detected, ending conversation"
                            )
                            self.conversation.mark_terminated()
                            return
                    except asyncio.TimeoutError:
                        self.conversation.logger.debug("Goodbye detection timed out")
            except asyncio.CancelledError:
                pass

    class FillerAudioWorker(InterruptibleWorker):
        def __init__(
            self,
            input_queue: asyncio.Queue[InterruptibleEvent[FillerAudio]],
            conversation: "StreamingConversation",
        ):
            self.input_queue = input_queue
            self.conversation = conversation
            self.current_filler_seconds_per_chunk: Optional[int] = None
            self.filler_audio_started_event: Optional[threading.Event] = None

        async def wait_for_filler_audio_to_finish(self):
            if not self.filler_audio_started_event.set():
                self.conversation.logger.debug(
                    "Not waiting for filler audio to finish since we didn't send any chunks"
                )
                return
            if self.current_task and not self.current_task.done():
                self.conversation.logger.debug("Waiting for filler audio to finish")
                await self.current_task
                self.conversation.logger.debug("Filler audio finished")

        def interrupt_current_filler_audio(self):
            self.interruptible_event and self.interruptible_event.interrupt()

        async def process(self, item: InterruptibleEvent[FillerAudio]):
            try:
                filler_audio = item.payload
                filler_synthesis_result = filler_audio.create_synthesis_result()
                self.current_filler_seconds_per_chunk = filler_audio.seconds_per_chunk
                if isinstance(
                    self.conversation.agent.get_agent_config().send_filler_audio,
                    FillerAudioConfig,
                ):
                    silence_threshold = (
                        self.conversation.agent.get_agent_config().send_filler_audio.silence_threshold_seconds
                    )
                else:
                    silence_threshold = FILLER_AUDIO_DEFAULT_SILENCE_THRESHOLD_SECONDS
                await asyncio.sleep(silence_threshold)
                self.conversation.logger.debug("Sending filler audio to output")
                self.filler_audio_started_event = threading.Event()
                await self.conversation.send_speech_to_output(
                    filler_audio.message.text,
                    filler_synthesis_result,
                    item.interruption_event,
                    filler_audio.seconds_per_chunk,
                    started_event=self.filler_audio_started_event,
                )
            except asyncio.CancelledError:
                pass

    class AgentResponsesWorker(InterruptibleWorker):
        def __init__(
            self,
            input_queue: asyncio.Queue[InterruptibleEvent[BaseMessage]],
            output_queue: asyncio.Queue[SynthesisResult],
            conversation: "StreamingConversation",
        ):
            self.input_queue = input_queue
            self.output_queue = output_queue
            self.conversation = conversation
            self.chunk_size = (
                get_chunk_size_per_second(
                    self.conversation.synthesizer.get_synthesizer_config().audio_encoding,
                    self.conversation.synthesizer.get_synthesizer_config().sampling_rate,
                )
                * TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS
            )

        async def process(self, item: InterruptibleEvent[BaseMessage]):
            try:
                agent_response = item.payload
                self.conversation.logger.debug("Synthesizing speech for message")
                self.conversation.current_synthesis_span = tracer.start_span(
                    SYNTHESIS_TRACE_NAME,
                    {
                        "synthesizer": str(
                            self.conversation.synthesizer.get_synthesizer_config().type
                        )
                    },
                )
                synthesis_result = await self.conversation.synthesizer.create_speech(
                    agent_response,
                    self.chunk_size,
                    bot_sentiment=self.conversation.bot_sentiment,
                )
                event = self.conversation.enqueue_interruptible_event(
                    payload=(agent_response, synthesis_result),
                    is_interruptible=item.is_interruptible,
                )
                self.output_queue.put_nowait(event)
            except asyncio.CancelledError:
                pass

    class SynthesisResultsWorker(InterruptibleWorker):
        def __init__(
            self,
            input_queue: asyncio.Queue[
                InterruptibleEvent[Tuple[BaseMessage, SynthesisResult]]
            ],
            conversation: "StreamingConversation",
        ):
            self.input_queue = input_queue
            self.conversation = conversation

        async def process(
            self, item: InterruptibleEvent[Tuple[BaseMessage, SynthesisResult]]
        ):
            try:
                message, synthesis_result = item.payload
                message_sent, cut_off = await self.conversation.send_speech_to_output(
                    message.text,
                    synthesis_result,
                    item.interruption_event,
                    TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS,
                )
                self.conversation.logger.debug("Message sent: {}".format(message_sent))
                if cut_off:
                    self.conversation.agent.update_last_bot_message_on_cut_off(
                        message_sent
                    )
                self.conversation.transcript.add_bot_message(
                    text=message_sent,
                    events_manager=self.conversation.events_manager,
                    conversation_id=self.conversation.id,
                )
            except asyncio.CancelledError:
                pass

    def __init__(
        self,
        output_device: BaseOutputDevice,
        transcriber: BaseTranscriber,
        agent: BaseAgent,
        synthesizer: BaseSynthesizer,
        conversation_id: str = None,
        per_chunk_allowance_seconds: int = PER_CHUNK_ALLOWANCE_SECONDS,
        events_manager: Optional[EventsManager] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.id = conversation_id or create_conversation_id()
        self.logger = logger or logging.getLogger(__name__)
        self.output_device = output_device
        self.transcriber = transcriber
        self.agent = agent
        self.synthesizer = synthesizer
        self.final_transcriptions_queue: asyncio.Queue[
            InterruptibleEvent[Transcription]
        ] = asyncio.Queue()
        self.agent_responses_queue: asyncio.Queue[
            InterruptibleEvent[Tuple[BaseMessage, bool]]
        ] = asyncio.Queue()
        self.synthesis_results_queue: asyncio.Queue[
            InterruptibleEvent[BaseMessage, SynthesisResult]
        ] = asyncio.Queue()
        self.filler_audio_queue: asyncio.Queue[
            InterruptibleEvent[FillerAudio]
        ] = asyncio.Queue()
        self.transcriptions_worker = self.TranscriptionsWorker(
            self.transcriber.output_queue, self.final_transcriptions_queue, self
        )
        self.final_transcriptions_worker = self.FinalTranscriptionsWorker(
            self.final_transcriptions_queue, self.agent_responses_queue, self
        )
        self.agent_responses_worker = self.AgentResponsesWorker(
            self.agent_responses_queue, self.synthesis_results_queue, self
        )
        self.synthesis_results_worker = self.SynthesisResultsWorker(
            self.synthesis_results_queue, self
        )
        self.filler_audio_worker = None
        if self.agent.get_agent_config().send_filler_audio:
            self.filler_audio_worker = self.FillerAudioWorker(
                self.filler_audio_queue, self
            )
        self.events_manager = events_manager or EventsManager()
        self.events_task = None
        self.per_chunk_allowance_seconds = per_chunk_allowance_seconds
        self.transcript = Transcript()
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
        if self.agent.get_agent_config().end_conversation_on_goodbye:
            self.goodbye_model = GoodbyeModel()

        self.is_human_speaking = False
        self.active = False
        self.interruptible_events: queue.Queue[InterruptibleEvent] = queue.Queue()
        self.mark_last_action_timestamp()

        self.check_for_idle_task = None
        self.track_bot_sentiment_task = None

        self.current_transcription_is_interrupt: bool = False

        # tracing
        self.current_synthesis_span: Optional[Span] = None
        self.start_time: float = None
        self.end_time: float = None

    async def start(self, mark_ready: Optional[Callable[[], Awaitable[None]]] = None):
        self.transcriber.start()
        self.transcriptions_worker.start()
        self.final_transcriptions_worker.start()
        self.agent_responses_worker.start()
        self.synthesis_results_worker.start()
        if self.filler_audio_worker:
            self.filler_audio_worker.start()
        is_ready = await self.transcriber.ready()
        if not is_ready:
            raise Exception("Transcriber startup failed")
        if self.agent.get_agent_config().send_filler_audio:
            filler_audio_config = (
                self.agent.get_agent_config().send_filler_audio
                if isinstance(
                    self.agent.get_agent_config().send_filler_audio, FillerAudioConfig
                )
                else FillerAudioConfig()
            )
            await self.synthesizer.set_filler_audios(filler_audio_config)
        self.agent.start()
        if mark_ready:
            await mark_ready()
        if self.agent.get_agent_config().initial_message:
            self.transcript.add_bot_message(
                text=self.agent.get_agent_config().initial_message.text,
                events_manager=self.events_manager,
                conversation_id=self.id,
            )
        if self.synthesizer.get_synthesizer_config().sentiment_config:
            self.update_bot_sentiment()
        if self.agent.get_agent_config().initial_message:
            event = self.enqueue_interruptible_event(
                payload=self.agent.get_agent_config().initial_message,
                is_interruptible=False,
            )
            self.agent_responses_queue.put_nowait(event)
        self.active = True
        if self.synthesizer.get_synthesizer_config().sentiment_config:
            self.track_bot_sentiment_task = asyncio.create_task(
                self.track_bot_sentiment()
            )
        self.check_for_idle_task = asyncio.create_task(self.check_for_idle())
        if len(self.events_manager.subscriptions) > 0:
            self.events_task = asyncio.create_task(self.events_manager.start())

    async def check_for_idle(self):
        while self.is_active():
            if time.time() - self.last_action_timestamp > (
                self.agent.get_agent_config().allowed_idle_time_seconds
                or ALLOWED_IDLE_TIME
            ):
                self.logger.debug("Conversation idle for too long, terminating")
                self.mark_terminated()
                return
            await asyncio.sleep(15)

    async def track_bot_sentiment(self):
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

    def receive_audio(self, chunk: bytes):
        self.transcriber.send_audio(chunk)

    def warmup_synthesizer(self):
        self.synthesizer.ready_synthesizer()

    def mark_last_action_timestamp(self):
        self.last_action_timestamp = time.time()

    def enqueue_interruptible_event(
        self, is_interruptible: bool = True, payload: Any = None
    ) -> InterruptibleEvent:
        interruptible_event = InterruptibleEvent(is_interruptible, payload)
        self.interruptible_events.put_nowait(interruptible_event)
        return interruptible_event

    def broadcast_interrupt(self):
        """Returns true if any events were interrupted"""
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
        self.agent_responses_worker.cancel_current_task()
        self.final_transcriptions_worker.cancel_current_task()
        return num_interrupts > 0

    # returns an estimate of what was sent up to, and a flag if the message was cut off
    async def send_speech_to_output(
        self,
        message: str,
        synthesis_result: SynthesisResult,
        stop_event: threading.Event,
        seconds_per_chunk: int,
        started_event: Optional[threading.Event] = None,
    ):
        message_sent = message
        cut_off = False
        chunk_size = seconds_per_chunk * get_chunk_size_per_second(
            self.synthesizer.get_synthesizer_config().audio_encoding,
            self.synthesizer.get_synthesizer_config().sampling_rate,
        )
        chunk_idx = 0
        async for chunk_result in synthesis_result.chunk_generator:
            start_time = time.time()
            speech_length_seconds = seconds_per_chunk * (
                len(chunk_result.chunk) / chunk_size
            )
            if stop_event.is_set():
                seconds = chunk_idx * seconds_per_chunk
                self.logger.debug(
                    "Interrupted, stopping text to speech after {} chunks".format(
                        chunk_idx
                    )
                )
                message_sent = f"{synthesis_result.get_message_up_to(seconds)}-"
                cut_off = True
                break
            if chunk_idx == 0:
                if self.current_synthesis_span:
                    self.current_synthesis_span.end()
                if started_event:
                    started_event.set()
            self.output_device.send_nonblocking(chunk_result.chunk)
            end_time = time.time()
            await asyncio.sleep(
                max(
                    speech_length_seconds
                    - (end_time - start_time)
                    - self.per_chunk_allowance_seconds,
                    0,
                )
            )
            self.logger.debug(
                "Sent chunk {} with size {}".format(chunk_idx, len(chunk_result.chunk))
            )
            self.mark_last_action_timestamp()
            chunk_idx += 1
        return message_sent, cut_off

    def mark_terminated(self):
        self.active = False

    # must be called from the main thread
    def terminate(self):
        self.mark_terminated()
        self.events_manager.publish_event(
            TranscriptCompleteEvent(
                conversation_id=self.id, transcript=self.transcript.to_string()
            )
        )
        if self.current_synthesis_span:
            self.logger.debug("Closing synthesizer span")
            self.current_synthesis_span.end()
        if self.check_for_idle_task:
            self.logger.debug("Terminating check_for_idle Task")
            self.check_for_idle_task.cancel()
        if self.track_bot_sentiment_task:
            self.logger.debug("Terminating track_bot_sentiment Task")
            self.track_bot_sentiment_task.cancel()
        if self.events_manager and self.events_task:
            self.logger.debug("Terminating events Task")
            self.events_manager.end()
        self.logger.debug("Terminating agent")
        self.agent.terminate()
        self.logger.debug("Terminating output device")
        self.output_device.terminate()
        self.logger.debug("Terminating speech transcriber")
        self.transcriber.terminate()
        self.logger.debug("Terminating transcriptions worker")
        self.transcriptions_worker.terminate()
        self.logger.debug("Terminating final transcriptions worker")
        self.final_transcriptions_worker.terminate()
        self.logger.debug("Terminating agent responses worker")
        self.agent_responses_worker.terminate()
        self.logger.debug("Terminating synthesis results worker")
        self.synthesis_results_worker.terminate()
        if self.filler_audio_worker:
            self.logger.debug("Terminating filler audio worker")
            self.filler_audio_worker.terminate()
        self.logger.debug("Successfully terminated")

    def is_active(self):
        return self.active
