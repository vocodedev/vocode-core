import asyncio
from typing import AsyncGenerator, Awaitable, Callable, Optional, Tuple
import logging
import time
import random

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
from vocode.streaming.utils import (
    create_conversation_id,
    create_loop_in_thread,
    get_chunk_size_per_second,
)
from vocode.streaming.transcriber.base_transcriber import (
    Transcription,
    BaseTranscriber,
)

tracer = trace.get_tracer(__name__)
SYNTHESIS_TRACE_NAME = "synthesis"
AGENT_TRACE_NAME = "agent"

# TODO(ajay)
# - interrupt LLM generation / flush queue on interrupt
# - fix no interrupt flow


class StreamingConversation:
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
        self.transcriber_task: asyncio.Task = None
        self.agent = agent
        self.consume_transcriptions_task: asyncio.Task = None
        self.consume_final_transcriptions_task: asyncio.Task = None
        self.final_transcriptions_queue: asyncio.Queue[Transcription] = asyncio.Queue()
        self.consume_agent_responses_task: asyncio.Task = None
        self.agent_responses_queue: asyncio.Queue[
            Tuple[BaseMessage, bool]
        ] = asyncio.Queue()
        self.synthesis_results_queue: asyncio.Queue[
            BaseMessage, SynthesisResult, asyncio.Event
        ] = asyncio.Queue()
        self.consume_synthesis_results_task: asyncio.Task = None
        self.synthesizer = synthesizer
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
        self.current_synthesis_task = None
        self.is_current_synthesis_interruptable = False
        self.stop_events: asyncio.Queue[asyncio.Event] = asyncio.Queue()
        self.last_action_timestamp = time.time()
        self.check_for_idle_task = None
        self.track_bot_sentiment_task = None
        self.should_wait_for_filler_audio_done_event = False
        self.current_filler_audio_done_event: Optional[asyncio.Event] = None
        self.current_filler_seconds_per_chunk: int = 0
        self.current_transcription_is_interrupt: bool = False

        # tracing
        self.current_synthesis_span: Optional[Span] = None
        self.current_agent_span: Optional[Span] = None
        self.start_time: float = None
        self.end_time: float = None

    async def start(self, mark_ready: Optional[Callable[[], Awaitable[None]]] = None):
        self.transcriber_task = asyncio.create_task(self.transcriber.run())
        self.consume_transcriptions_task = asyncio.create_task(
            self.consume_transcriptions()
        )
        self.consume_final_transcriptions_task = asyncio.create_task(
            self.consume_final_transcriptions()
        )
        self.consume_agent_responses_task = asyncio.create_task(
            self.consume_agent_responses()
        )
        self.consume_synthesis_results_task = asyncio.create_task(
            self.consume_synthesis_results()
        )
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
            self.agent_responses_queue.put_nowait(
                (
                    self.agent.get_agent_config().initial_message,
                    False,
                    self.enqueue_stop_event(),
                )
            )
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

    async def consume_transcriptions(self):
        while self.active:
            transcription = await self.transcriber.get_output_queue().get()
            self.last_action_timestamp = time.time()
            if transcription.is_final:
                self.logger.debug(
                    "Got transcription: {}, confidence: {}".format(
                        transcription.message, transcription.confidence
                    )
                )
            if not self.is_human_speaking and transcription.confidence > (
                self.transcriber.get_transcriber_config().min_interrupt_confidence or 0
            ):
                # send interrupt
                self.current_transcription_is_interrupt = False
                if self.is_current_synthesis_interruptable:
                    self.logger.debug("sending interrupt")
                    self.current_transcription_is_interrupt = (
                        self.interrupt_all_synthesis()
                    )
                self.logger.debug("Human started speaking")

            transcription.is_interrupt = self.current_transcription_is_interrupt
            self.is_human_speaking = not transcription.is_final
            if transcription.is_final:
                self.final_transcriptions_queue.put_nowait(transcription)

    async def consume_final_transcriptions(self):
        while self.active:
            transcription = await self.final_transcriptions_queue.get()
            self.transcript.add_human_message(
                text=transcription.message,
                events_manager=self.events_manager,
                conversation_id=self.id,
            )
            goodbye_detected_task = None
            if self.agent.get_agent_config().end_conversation_on_goodbye:
                goodbye_detected_task = asyncio.create_task(
                    self.goodbye_model.is_goodbye(transcription.message)
                )
            if self.agent.get_agent_config().send_filler_audio:
                self.logger.debug("Sending filler audio")
                if self.synthesizer.filler_audios:
                    filler_audio = random.choice(self.synthesizer.filler_audios)
                    self.logger.debug(f"Chose {filler_audio.message.text}")
                    self.current_filler_audio_done_event = asyncio.Event()
                    self.current_filler_seconds_per_chunk = (
                        filler_audio.seconds_per_chunk
                    )
                    stop_event = self.enqueue_stop_event()
                    asyncio.create_task(
                        self.send_filler_audio_to_output(
                            filler_audio,
                            stop_event,
                            done_event=self.current_filler_audio_done_event,
                        )
                    )
                else:
                    self.logger.debug("No filler audio available for synthesizer")
            self.logger.debug("Generating response for transcription")
            if self.agent.get_agent_config().generate_responses:
                responses = self.agent.generate_response(
                    transcription.message,
                    is_interrupt=transcription.is_interrupt,
                    conversation_id=self.id,
                )
                stop_event = self.enqueue_stop_event()
                should_wait_for_filler_audio = (
                    self.agent.get_agent_config().send_filler_audio
                )
                async for response in responses:
                    if should_wait_for_filler_audio:
                        self.interrupt_all_synthesis()
                        await self.wait_for_filler_audio_to_finish()
                        should_wait_for_filler_audio = False
                    self.agent_responses_queue.put_nowait(
                        (
                            BaseMessage(text=response),
                            self.agent.get_agent_config().allow_agent_to_be_cut_off,
                            stop_event,
                        )
                    )
            else:
                try:
                    with tracer.start_span(
                        AGENT_TRACE_NAME, {"generate_response": False}
                    ):
                        response, should_stop = await self.agent.respond(
                            transcription.message,
                            is_interrupt=transcription.is_interrupt,
                            conversation_id=self.id,
                        )
                except Exception as e:
                    self.logger.error(
                        f"Error while generating response: {e}", exc_info=True
                    )
                    response = None
                    should_stop = True
                if self.agent.get_agent_config().send_filler_audio:
                    self.interrupt_all_synthesis()
                    await self.wait_for_filler_audio_to_finish()
                if should_stop:
                    self.logger.debug("Agent requested to stop")
                    self.mark_terminated()
                    return
                if response:
                    self.agent_responses_queue.put_nowait(
                        (
                            BaseMessage(text=response),
                            self.agent.get_agent_config().allow_agent_to_be_cut_off,
                            self.enqueue_stop_event(),
                        )
                    )
                else:
                    self.logger.debug("No response generated")
            if goodbye_detected_task:
                try:
                    goodbye_detected = await asyncio.wait_for(
                        goodbye_detected_task, 0.1
                    )
                    if goodbye_detected:
                        self.logger.debug("Goodbye detected, ending conversation")
                        self.mark_terminated()
                        return
                except asyncio.TimeoutError:
                    self.logger.debug("Goodbye detection timed out")

    async def consume_agent_responses(self):
        chunk_size = (
            get_chunk_size_per_second(
                self.synthesizer.get_synthesizer_config().audio_encoding,
                self.synthesizer.get_synthesizer_config().sampling_rate,
            )
            * TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS
        )
        while self.active:
            agent_response: Tuple[
                BaseMessage, bool, asyncio.Event
            ] = await self.agent_responses_queue.get()
            (
                message,
                should_allow_human_to_cut_off_bot,
                stop_event,
            ) = agent_response
            if stop_event.is_set():
                continue
            self.is_current_synthesis_interruptable = should_allow_human_to_cut_off_bot
            self.logger.debug("Synthesizing speech for message")
            self.current_synthesis_span = tracer.start_span(
                SYNTHESIS_TRACE_NAME,
                {"synthesizer": str(self.synthesizer.get_synthesizer_config().type)},
            )
            synthesis_result = await self.synthesizer.create_speech(
                message, chunk_size, bot_sentiment=self.bot_sentiment
            )
            self.synthesis_results_queue.put_nowait(
                (message, synthesis_result, stop_event)
            )

    async def consume_synthesis_results(self):
        while self.active:
            queue_element = await self.synthesis_results_queue.get()
            (message, synthesis_result, stop_event) = queue_element
            message_sent, cut_off = await self.send_speech_to_output(
                message.text,
                synthesis_result,
                stop_event,
                TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS,
            )
            self.logger.debug("Message sent: {}".format(message_sent))
            if cut_off:
                self.agent.update_last_bot_message_on_cut_off(message_sent)
            self.transcript.add_bot_message(
                text=message_sent,
                events_manager=self.events_manager,
                conversation_id=self.id,
            )

    def enqueue_stop_event(self):
        stop_event = asyncio.Event()
        self.stop_events.put_nowait(stop_event)
        return stop_event

    def interrupt_all_synthesis(self):
        """Returns true if any synthesis was interrupted"""
        num_interrupts = 0
        while True:
            try:
                stop_event = self.stop_events.get_nowait()
                if not stop_event.is_set():
                    self.logger.debug("Interrupting synthesis")
                    stop_event.set()
                    num_interrupts += 1
            except asyncio.QueueEmpty:
                break
        return num_interrupts > 0

    # returns an estimate of what was sent up to, and a flag if the message was cut off
    async def send_speech_to_output(
        self,
        message: str,
        synthesis_result: SynthesisResult,
        stop_event: asyncio.Event,
        seconds_per_chunk: int,
        is_filler_audio: bool = False,
    ):
        message_sent = message
        cut_off = False
        chunk_size = seconds_per_chunk * get_chunk_size_per_second(
            self.synthesizer.get_synthesizer_config().audio_encoding,
            self.synthesizer.get_synthesizer_config().sampling_rate,
        )
        chunk_idx = True
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
                if is_filler_audio:
                    self.should_wait_for_filler_audio_done_event = True
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
            self.last_action_timestamp = time.time()
            chunk_idx += 1
        return message_sent, cut_off

    async def send_filler_audio_to_output(
        self,
        filler_audio: FillerAudio,
        stop_event: asyncio.Event,
        done_event: asyncio.Event,
    ):
        filler_synthesis_result = filler_audio.create_synthesis_result()
        self.is_current_synthesis_interruptable = filler_audio.is_interruptable
        if isinstance(
            self.agent.get_agent_config().send_filler_audio, FillerAudioConfig
        ):
            silence_threshold = (
                self.agent.get_agent_config().send_filler_audio.silence_threshold_seconds
            )
        else:
            silence_threshold = FILLER_AUDIO_DEFAULT_SILENCE_THRESHOLD_SECONDS
        await asyncio.sleep(silence_threshold)
        self.logger.debug("Sending filler audio to output")
        await self.send_speech_to_output(
            filler_audio.message.text,
            filler_synthesis_result,
            stop_event,
            filler_audio.seconds_per_chunk,
            is_filler_audio=True,
        )
        done_event.set()

    async def wait_for_filler_audio_to_finish(self):
        if not self.should_wait_for_filler_audio_done_event:
            self.logger.debug(
                "Not waiting for filler audio to finish since we didn't send any chunks"
            )
            return
        self.should_wait_for_filler_audio_done_event = False
        if (
            self.current_filler_audio_done_event
            and not self.current_filler_audio_done_event.is_set()
        ):
            self.logger.debug("Waiting for filler audio to finish")
            # this should guarantee that filler audio finishes, since it has to be on its last chunk
            if not await self.current_filler_audio_done_event.wait(
                self.current_filler_seconds_per_chunk
            ):
                self.logger.debug("Filler audio did not finish")

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
        if self.current_agent_span:
            self.logger.debug("Closing agent span")
            self.current_agent_span.end()
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
        self.logger.debug("Terminating transcriber task")
        self.transcriber_task.cancel()
        self.logger.debug("Terminating consume transcriptions task")
        self.consume_transcriptions_task.cancel()
        self.logger.debug("Terminating consume final transcriptions task")
        self.consume_final_transcriptions_task.cancel()
        self.logger.debug("Terminating consume agent responses task")
        self.consume_agent_responses_task.cancel()
        self.logger.debug("Terminating consume synthesis results task")
        self.consume_synthesis_results_task.cancel()
        self.logger.debug("Successfully terminated")

    def is_active(self):
        return self.active
