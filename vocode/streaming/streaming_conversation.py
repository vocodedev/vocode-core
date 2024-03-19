from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
import typing
from typing import Any, Awaitable, Callable, Generic, Optional, Tuple, TypeVar

from azure.ai.textanalytics.aio import TextAnalyticsClient

from vocode.streaming.action.worker import ActionsWorker
from vocode.streaming.agent.base_agent import (
    AgentInput,
    AgentResponse,
    AgentResponseFillerAudio,
    AgentResponseMessage,
    AgentResponseStop,
    BaseAgent,
    TranscriptionAgentInput,
)
from vocode.streaming.agent.bot_sentiment_analyser import (
    BotSentimentAnalyser,
)
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent, ChatGPTAgentOld
from vocode.streaming.constants import (
    TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS,
    PER_CHUNK_ALLOWANCE_SECONDS,
    ALLOWED_IDLE_TIME,
)
from vocode.streaming.ignored_while_talking_fillers_fork import OpenAIEmbeddingOverTalkingFillerDetector
from vocode.streaming.input_device.stream_handler import AudioStreamHandler
from vocode.streaming.models.agent import FillerAudioConfig
from vocode.streaming.models.events import Sender, EventType
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import (
    SentimentConfig, )
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.models.transcript import (
    Message,
    Transcript,
    TranscriptCompleteEvent, )
from vocode.streaming.output_device.base_output_device import BaseOutputDevice
from vocode.streaming.response_classifier import OpenaiEmbeddingsResponseClassifier
from vocode.streaming.synthesizer import ElevenLabsSynthesizer
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    FillerAudio,
)
from vocode.streaming.transcriber.base_transcriber import (
    Transcription,
    BaseTranscriber,
)
from vocode.streaming.utils import create_conversation_id, get_chunk_size_per_second
from vocode.streaming.utils.conversation_logger_adapter import wrap_logger
from vocode.streaming.utils.events_manager import EventsManager, RedisEventsManager
from vocode.streaming.utils.state_manager import ConversationStateManager
from vocode.streaming.utils.worker import (
    AsyncQueueWorker,
    InterruptibleAgentResponseWorker,
    InterruptibleEvent,
    InterruptibleEventFactory,
    InterruptibleAgentResponseEvent,
)

BOT_TALKING_SINCE_LAST_FILLER_TIME_LIMIT = 3.0
BOT_TALKING_SINCE_LAST_ACTION_TIME_LIMIT = 0.1

OutputDeviceType = TypeVar("OutputDeviceType", bound=BaseOutputDevice)


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

    class TranscriptionsWorker(AsyncQueueWorker):
        """Processes all transcriptions: sends an interrupt if needed
        and sends final transcriptions to the output queue"""

        def __init__(
                self,
                input_queue: asyncio.Queue[Transcription],
                output_queue: asyncio.Queue[InterruptibleEvent[AgentInput]],
                conversation: "StreamingConversation",
                interruptible_event_factory: InterruptibleEventFactory,
                let_bot_finish_speaking: bool = True,
        ):
            super().__init__(input_queue, output_queue)
            self.input_queue = input_queue
            self.output_queue = output_queue
            self.conversation = conversation
            self.interruptible_event_factory = interruptible_event_factory
            self.let_bot_finish_speaking = let_bot_finish_speaking

        async def process(self, transcription: Transcription):
            self.conversation.logger.info(
                f"Got transcription event: {transcription.message}, {transcription.confidence}, {transcription.is_final}, {transcription.is_interrupt}")
            if transcription.message.strip() == "":
                # This is often received when the person starts talking. We don't know if they will use filler word.
                # TODO set a timer here, if transcription does not arrive on time, assume the person keeps talking and need to interrupt the bot.
                # TODO human_speaking should be set here as this is the only place with is_final=false.
                self.conversation.logger.info(f"Ignoring empty transcription {transcription}")
                return

            # Prevent interrupt.
            since_last_filler_time = time.time() - self.conversation.last_filler_timestamp
            silence_since_last_action = time.time() - self.conversation.last_action_timestamp
            if (
                    since_last_filler_time < self.conversation.filler_audio_config.silence_threshold_seconds + BOT_TALKING_SINCE_LAST_FILLER_TIME_LIMIT
                    or silence_since_last_action < BOT_TALKING_SINCE_LAST_ACTION_TIME_LIMIT):
                # I could clear since_last_filler_time after first response is generated in the synthesizer, but this is complicated to detect, which audio is which.
                bot_still_talking = True
                self.conversation.logger.info(
                    f'Bot still talking, because filler was said recently. since_last_filler_time: {since_last_filler_time}, silence_since_last_action: {silence_since_last_action}')

            else:
                has_task = self.conversation.synthesis_results_worker.current_task is not None
                bot_still_talking = has_task and not self.conversation.synthesis_results_worker.current_task.done() if has_task else False

            if bot_still_talking and self.let_bot_finish_speaking:
                self.conversation.logger.info(
                    f'The user said "{transcription.message}" during the bot was talking. We are letting the bot finish speaking. Message is not sent to the agent.')
                # Detect if the bot is talking. This may fail if the current task is done and another not started yet. But playing the audio takes most of the time.
                return  # just ignore the transcription for now.

            if bot_still_talking and self.conversation.over_talking_filler_detector:
                self.conversation.logger.info(
                    f'The user said "{transcription.message}" during the bot was talking. Testing to ignore filler words and confirmation words.')
                if self.conversation.over_talking_filler_detector.detect_filler(transcription.message):
                    return

            if transcription.is_final:
                self.conversation.logger.debug(
                    "Got transcription {}, confidence: {}, is_final: {}".format(
                        transcription.message, transcription.confidence, transcription.is_final
                    )
                )

            if (
                    not self.conversation.is_human_speaking
                    and self.conversation.is_interrupt(transcription)
            ):
                self.conversation.current_transcription_is_interrupt = (
                    self.conversation.broadcast_interrupt()
                )
                if self.conversation.current_transcription_is_interrupt:
                    self.conversation.logger.debug("sending interrupt")

            transcription.is_interrupt = (
                self.conversation.current_transcription_is_interrupt
            )
            self.conversation.is_human_speaking = not transcription.is_final
            if transcription.is_final:
                self.conversation.mark_last_action_timestamp()
                # we use getattr here to avoid the dependency cycle between VonageCall and StreamingConversation

                event = self.interruptible_event_factory.create_interruptible_event(
                    TranscriptionAgentInput(
                        transcription=transcription,
                        conversation_id=self.conversation.id,
                        vonage_uuid=getattr(self.conversation, "vonage_uuid", None),
                        twilio_sid=getattr(self.conversation, "twilio_sid", None),
                    )
                )
                self.output_queue.put_nowait(event)
                self.conversation.logger.info(f"USER: {transcription.message}")

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
                silence_threshold = (
                    self.conversation.filler_audio_config.silence_threshold_seconds
                )
                filler_synthesis_result = filler_audio.create_synthesis_result()
                self.current_filler_seconds_per_chunk = filler_audio.seconds_per_chunk
                await asyncio.sleep(silence_threshold)
                self.conversation.logger.debug("Sending filler audio to output")
                self.conversation.logger.info(f"BOT (filler): {filler_audio.message.text}")
                self.filler_audio_started_event = threading.Event()
                await self.conversation.send_speech_to_output(
                    filler_audio.message.text,
                    filler_synthesis_result,
                    item.interruption_event,
                    filler_audio.seconds_per_chunk,
                    started_event=self.filler_audio_started_event,
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
            self.chunk_size = (
                    get_chunk_size_per_second(
                        self.conversation.synthesizer.get_synthesizer_config().audio_encoding,
                        self.conversation.synthesizer.get_synthesizer_config().sampling_rate,
                    )
                    * TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS
            )

        def send_filler_audio(self, agent_response_tracker: Optional[asyncio.Event], filler_audio: FillerAudio,
                              ):
            if self.conversation.filler_audio_worker is None:
                raise ValueError("filler_audio_worker is None, must be set")

            self.conversation.logger.info(f"Chose {filler_audio.message.text}")
            event = self.interruptible_event_factory.create_interruptible_agent_response_event(
                filler_audio,
                is_interruptible=filler_audio.is_interruptible,
                agent_response_tracker=agent_response_tracker,
            )
            self.conversation.filler_audio_worker.consume_nonblocking(event)

        async def process(self, item: InterruptibleAgentResponseEvent[AgentResponse]):
            if not self.conversation.synthesis_enabled:
                self.conversation.logger.debug(
                    "Synthesis disabled, not synthesizing speech"
                )
                return
            try:
                self.conversation.mark_last_action_timestamp()  # received agent response.
                agent_response = item.payload

                if isinstance(agent_response, AgentResponseFillerAudio):
                    if hasattr(self.conversation.synthesizer, "pick_filler"):
                        user_message = agent_response.transcript
                        if "THIS IS SYSTEM MESSAGE:" in user_message:  # no filler if this is a system message.
                            return

                        self.conversation.mark_last_filler_timestamp()
                        bot_message = self.conversation.transcript.get_last_bot_text()
                        self.conversation.synthesizer: ElevenLabsSynthesizer
                        picked = await self.conversation.synthesizer.pick_filler(bot_message, user_message)
                        if picked is not None:
                            self.send_filler_audio(item.agent_response_tracker, picked)
                        return
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
                start_time = time.time()
                synthesis_result = await self.conversation.synthesizer.create_speech(
                    agent_response_message.message,
                    self.chunk_size,
                    bot_sentiment=self.conversation.bot_sentiment,
                )
                self.conversation.mark_last_action_timestamp()  # once speech started creating.
                end_time = time.time()
                self.conversation.logger.info(
                    "Getting response from Synth took {} seconds".format(end_time - start_time))
                self.produce_interruptible_agent_response_event_nonblocking(
                    (agent_response_message.message, synthesis_result),
                    is_interruptible=item.is_interruptible,
                    agent_response_tracker=item.agent_response_tracker,
                )

            except asyncio.CancelledError:
                pass

    class SynthesisResultsWorker(InterruptibleAgentResponseWorker):
        """Plays SynthesisResults from the output queue on the output device"""

        def __init__(
                self,
                input_queue: asyncio.Queue[
                    InterruptibleAgentResponseEvent[Tuple[BaseMessage, SynthesisResult]]
                ],
                conversation: "StreamingConversation",
        ):
            super().__init__(input_queue=input_queue)
            self.input_queue = input_queue
            self.conversation = conversation

            self.goodbye_token = "<ENDCALL>"  # FIXME PARAMETRIZE

        async def custom_goodbye(self, message: BaseMessage):
            if message.text == self.goodbye_token:
                await self.goodbye_terminate()

        async def goodbye_terminate(self):
            self.conversation.logger.info(
                "Agent said goodbye, ending call"
            )
            await self.conversation.terminate()

        async def process(
                self,
                item: InterruptibleAgentResponseEvent[Tuple[BaseMessage, SynthesisResult]],
        ):
            try:
                message, synthesis_result = item.payload
                # create an empty transcript message and attach it to the transcript
                await self.custom_goodbye(message)
                transcript_message = Message(
                    text="",
                    sender=Sender.BOT,
                )
                self.conversation.transcript.add_message(
                    message=transcript_message,
                    conversation_id=self.conversation.id,
                    publish_to_events_manager=False,
                )
                message_sent, cut_off = await self.conversation.send_speech_to_output(
                    message.text,
                    synthesis_result,
                    item.interruption_event,
                    TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS,
                    transcript_message=transcript_message,
                )
                # publish the transcript message now that it includes what was said during send_speech_to_output
                self.conversation.transcript.maybe_publish_transcript_event_from_message(
                    message=transcript_message,
                    conversation_id=self.conversation.id,
                )
                # redis call here
                if self.conversation.redis_event_manger is not None:
                    self.conversation.transcript.publish_redis_transcript_event_from_message(
                        message=transcript_message
                    )
                item.agent_response_tracker.set()
                if cut_off:
                    self.conversation.agent.update_last_bot_message_on_cut_off(
                        message_sent
                    )
                if self.conversation.agent.agent_config.end_conversation_on_goodbye:
                    goodbye_detected_task = (
                        self.conversation.agent.create_goodbye_detection_task(
                            message_sent
                        )
                    )
                    try:
                        if await asyncio.wait_for(goodbye_detected_task, 0.1):
                            await self.goodbye_terminate()
                    except asyncio.TimeoutError:
                        pass
            except asyncio.CancelledError:
                pass

    def __init__(
            self,
            output_device: OutputDeviceType,
            transcriber: BaseTranscriber[TranscriberConfig],
            agent: BaseAgent,
            synthesizer: BaseSynthesizer,
            text_analysis_client: Optional[TextAnalyticsClient] = None,
            conversation_id: Optional[str] = None,
            per_chunk_allowance_seconds: float = PER_CHUNK_ALLOWANCE_SECONDS,
            events_manager: Optional[EventsManager] = None,
            logger: Optional[logging.Logger] = None,
            over_talking_filler_detector: Optional[OpenAIEmbeddingOverTalkingFillerDetector] = None,
            openai_embeddings_response_classifier: Optional[OpenaiEmbeddingsResponseClassifier] = None,
            post_call_callback: Optional[Callable[[StreamingConversation], typing.Coroutine[None]]] = None,
    ):
        self.id = conversation_id or create_conversation_id()
        self.logger = wrap_logger(
            logger or logging.getLogger(__name__),
            conversation_id=self.id,
        )
        self.logger.info("Creating conversation")
        self.call_start = time.time()
        self.call_initial_delay = 1.5
        self.output_device = output_device
        self.transcriber = transcriber
        self.audio_stream_handler = None  # FIXME: try to set it here or in the start method in the beginning.
        self.agent = agent
        self.synthesizer = synthesizer
        self.synthesis_enabled = True
        self.text_analysis_client = text_analysis_client

        self.post_call_callback = post_call_callback

        self.over_talking_filler_detector = over_talking_filler_detector
        self.openai_embeddings_response_classifier = openai_embeddings_response_classifier

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
        self.redis_event_manger = None
        try:
            self.redis_event_manger = RedisEventsManager(
                session_id=self.id,
                subscriptions=[EventType.TRANSCRIPT, EventType.DIALOG_STATE, EventType.TRANSCRIPT_COMPLETE,
                               EventType.FOLLOW_UP,
                               EventType.GPT_RESPONSE])
            # attach it to transript.
        except Exception as e:
            self.redis_event_manger = None
            self.logger.error(f"Failed to create RedisEventsManager: {e}. Not logging events to Redis.")

        self.events_task: Optional[asyncio.Task] = None
        self.redis_task: Optional[asyncio.Task] = None
        self.per_chunk_allowance_seconds = per_chunk_allowance_seconds
        self.transcript = Transcript()
        self.transcript.attach_events_manager(self.events_manager)
        self.transcript.attach_redis_events_manager(self.redis_event_manger)
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
        self.terminate_called = False

        self.last_action_timestamp = 0.0
        self.mark_last_action_timestamp()

        self.last_filler_timestamp = 0.0
        self.mark_last_filler_timestamp()

        self.check_for_idle_task: Optional[asyncio.Task] = None
        self.track_bot_sentiment_task: Optional[asyncio.Task] = None

        self.current_transcription_is_interrupt: bool = False

        # tracing
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.logger.info("Finished creating conversation")

    def create_state_manager(self) -> ConversationStateManager:
        return ConversationStateManager(conversation=self)

    def reconstruct_synthesis_result(self, filepath, message, chunk_size):
        # You would probably need to convert this raw data back to a file-like object or the expected 'Any' type
        return self.synthesizer.create_synthesis_result_from_wav(filepath, message, chunk_size)

    async def handle_initial_audio(self, initial_audio_path: str, initial_message: BaseMessage):
        # load audio
        self.logger.info(f"Loading initial audio from {initial_audio_path}")
        # There is wav here, but I could have various outputs. Do I need that chunking?
        # synth_result = self.reconstruct_synthesis_result(initial_audio_path, initial_message,
        assert initial_audio_path.endswith(
            self.synthesizer.synthesizer_config.output_format_to_cache_file_extension()), "File extension must be correct."
        assert isinstance(self.synthesizer, ElevenLabsSynthesizer), "Only ElevenLabsSynthesizer is supported."
        self.synthesizer: ElevenLabsSynthesizer
        with open(initial_audio_path, 'rb') as f:
            audio_data = f.read()

        synth_result = self.synthesizer.create_synthesis_result_from_bytes(audio_data, initial_message,
                                                                           self.agent_responses_worker.chunk_size)

        self.transcriber.mute()
        elapsed_time = time.time() - self.call_start
        remaining_time = self.call_initial_delay - elapsed_time
        self.logger.info(f"Waiting for {remaining_time} seconds before sending initial message")
        # Wait for the remaining time if it is positive
        if remaining_time > 0:
            await asyncio.sleep(remaining_time)

        initial_message_tracker = asyncio.Event()
        self.agent_responses_worker.produce_interruptible_agent_response_event_nonblocking(
            (initial_message, synth_result),
            is_interruptible=False,
            agent_response_tracker=initial_message_tracker,
        )
        await initial_message_tracker.wait()
        self.transcriber.unmute()

    async def start(self, mark_ready: Optional[Callable[[], Awaitable[None]]] = None):
        self.logger.info("Starting conversation")
        self.transcriber.start()
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
            await self.synthesizer.set_filler_audios(self.filler_audio_config)

        self.agent.start()
        initial_message = self.agent.get_agent_config().initial_message
        initial_audio_path = self.agent.get_agent_config().initial_audio_path
        self.agent.attach_transcript(self.transcript)

        if initial_audio_path and initial_message:
            asyncio.create_task(self.handle_initial_audio(initial_audio_path=initial_audio_path,
                                                          initial_message=initial_message))
        elif initial_message:
            # FIXME: use collator like in the agent.
            initial_message_generator = [x for x in initial_message.text.split(".") if x.strip() != ""]
            for message in initial_message_generator:
                message = BaseMessage(text=f'{message}.')
                asyncio.create_task(self.send_initial_message(message))
        elif isinstance(self.agent, ChatGPTAgentOld):
            self.logger.info("Creating first response")
            first_response_generator = self.agent.create_first_response()
            self.logger.info("Got generator")
            async for response in first_response_generator:
                self.logger.info(response)
                asyncio.create_task(self.send_initial_message(BaseMessage(text=response[0])))  # returns tuple.
        self.audio_stream_handler = AudioStreamHandler(conversation_id=self.id, transcriber=self.transcriber)
        await self.audio_stream_handler.post_init()
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

        if self.redis_event_manger is not None:
            self.redis_task = asyncio.create_task(self.redis_event_manger.start())
        self.logger.info("Conversation started")

    async def send_initial_message(self, initial_message: BaseMessage):
        # TODO: configure if initial message is interruptible
        self.transcriber.mute()
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
        """Asks if user still here."""
        while self.is_active():
            self.logger.info("Checking for idle")
            if time.time() - self.last_action_timestamp > (
                    self.agent.get_agent_config().allowed_idle_time_seconds
                    or ALLOWED_IDLE_TIME
            ):
                self.logger.info("Conversation idle for too long")
                # TODO: parametrize this message.
                transcription = Transcription(
                    message="THIS IS SYSTEM MESSAGE: Conversation idle for too long. If conversation is in czech " + \
                            "SAY: Slyšíme se? Jste ještě na lince?" + \
                            "If conversation is in english SAY: Are you still there?" + \
                            "If conversation is in slovak SAY: Ste ešte na linke?" + \
                            "If conversation is in polish SAY: Czy nadal tam jesteś?",
                    confidence=1.0,
                    is_final=True,
                    is_interrupt=True)
                self.transcriptions_worker.consume_nonblocking(transcription)
            await asyncio.sleep(2)  # checks every 2 seconds

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
        self.transcriptions_worker.consume_nonblocking(transcription)

    async def receive_audio(self, chunk: bytes):
        # TODO: refactor this, its not needed anymore, i can use just audio_stream_handler.
        await self.audio_stream_handler.receive_audio(chunk)

    def warmup_synthesizer(self):
        self.synthesizer.ready_synthesizer()

    def mark_last_action_timestamp(self):
        self.last_action_timestamp = time.time()

    def mark_last_filler_timestamp(self):
        """ Used to prevent noisy calls interrupting after fillers, but passing after other actions like Are You There. """
        self.last_filler_timestamp = time.time()

    def broadcast_interrupt(self):
        """Stops all inflight events and cancels all workers that are sending output

        Returns true if any events were interrupted - which is used as a flag for the agent (is_interrupt)
        """
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
        self.agent.cancel_current_task()
        self.agent_responses_worker.cancel_current_task()

        self.logger.info(f"Broadcasting interrupt. Cancelled {num_interrupts} interruptible events.")

        # Clearing these queues cuts time from finishing interruption talking to bot talking cut by 1 second from ~4.5 to ~3.5 seconds.
        self.clear_queue(self.agent.output_queue, 'agent.output_queue')
        self.clear_queue(self.agent_responses_worker.output_queue, 'agent_responses_worker.output_queue')
        self.clear_queue(self.agent_responses_worker.input_queue, 'agent_responses_worker.input_queue')
        if hasattr(self.output_device, 'queue'):
            self.clear_queue(self.output_device.queue, 'output_device.queue')
        # TODO clearing of the miniaudio queue may not be needed if the task is cancelled agent_responses_worker.cancel_current_task.
        # if isinstance(self.synthesizer, ElevenLabsSynthesizer) and self.synthesizer.miniaudio_worker is not None:
        #     self.clear_queue(self.synthesizer.miniaudio_worker.input_queue, 'synthesizer.miniaudio_worker.input_queue')
        #     self.clear_queue(self.synthesizer.miniaudio_worker.output_queue, 'synthesizer.miniaudio_worker.output_queue')
        #     # stop the worker with sentinel
        #     self.synthesizer.miniaudio_worker.consume_nonblocking(None)

        return num_interrupts > 0

    def is_interrupt(self, transcription: Transcription):
        return transcription.confidence >= (
                self.transcriber.get_transcriber_config().min_interrupt_confidence or 0
        )

    @staticmethod
    def clear_queue(q: asyncio.Queue, queue_name: str):
        while not q.empty():
            logging.info(f'Clearing queue {queue_name} with size {q.qsize()}')
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                continue

    async def send_speech_to_output(
            self,
            message: str,
            synthesis_result: SynthesisResult,
            stop_event: threading.Event,
            seconds_per_chunk: int,
            transcript_message: Optional[Message] = None,
            started_event: Optional[threading.Event] = None,
    ):
        """
        - Sends the speech chunk by chunk to the output device
          - update the transcript message as chunks come in (transcript_message is always provided for non filler audio utterances)
        - If the stop_event is set, the output is stopped
        - Sets started_event when the first chunk is sent

        Importantly, we rate limit the chunks sent to the output. For interrupts to work properly,
        the next chunk of audio can only be sent after the last chunk is played, so we send
        a chunk of x seconds only after x seconds have passed since the last chunk was sent.

        Returns the message that was sent up to, and a flag if the message was cut off
        """
        if self.transcriber.get_transcriber_config().mute_during_speech:
            self.logger.debug("Muting transcriber")
            self.transcriber.mute()
        message_sent = message
        cut_off = False
        chunk_size = seconds_per_chunk * get_chunk_size_per_second(
            self.synthesizer.get_synthesizer_config().audio_encoding,
            self.synthesizer.get_synthesizer_config().sampling_rate,
        )
        chunk_idx = 0
        seconds_spoken = 0

        generating_start_time = time.time()
        first_chunk = True
        async for chunk_result in synthesis_result.chunk_generator:
            self.mark_last_action_timestamp()  # once speech started consuming from synthesizer.
            if first_chunk:
                generating_end_time = time.time()
                first_chunk = False
                self.logger.info(
                    f"Generating first chunk took {generating_end_time - generating_start_time} seconds for message {message}")

            start_time = time.time()
            speech_length_seconds = seconds_per_chunk * (
                    len(chunk_result.chunk) / chunk_size
            )
            seconds_spoken = chunk_idx * seconds_per_chunk
            if stop_event.is_set():
                self.logger.debug(
                    "Interrupted, stopping text to speech after {} chunks".format(
                        chunk_idx
                    )
                )
                message_sent = f"{synthesis_result.get_message_up_to(seconds_spoken)}-"
                self.logger.info(f"Interrupted agent said: {message_sent}")
                cut_off = True
                break
            if chunk_idx == 0:
                if started_event:
                    started_event.set()
            self.output_device.consume_nonblocking(chunk_result.chunk)
            end_time = time.time()
            await asyncio.sleep(
                max(
                    speech_length_seconds
                    - (end_time - start_time)
                    - self.per_chunk_allowance_seconds,
                    0,
                )
            )
            self.mark_last_action_timestamp()
            chunk_idx += 1
            seconds_spoken += seconds_per_chunk
            if transcript_message:
                transcript_message.text = synthesis_result.get_message_up_to(
                    seconds_spoken
                )
        if self.transcriber.get_transcriber_config().mute_during_speech:
            self.logger.debug("Unmuting transcriber")
            self.transcriber.unmute()
        if transcript_message:
            transcript_message.text = message_sent
        return message_sent, cut_off

    def mark_terminated(self):
        self.active = False

    async def terminate(self):
        if self.terminate_called:
            self.logger.warning("Terminate already called. Ignoring.")
            return
        self.mark_terminated()
        self.terminate_called = True
        self.broadcast_interrupt()
        self.events_manager.publish_event(
            TranscriptCompleteEvent(conversation_id=self.id, transcript=self.transcript)
        )
        self.logger.info("Saving audio")
        self.audio_stream_handler.save_debug_audios()
        self.logger.info("audio saved")
        if self.audio_stream_handler.vad_wrapper:
            self.audio_stream_handler.vad_wrapper.reset_states()
            self.logger.info("Reset VAD model states")
        if self.redis_event_manger is not None:
            self.redis_event_manger.publish_event(
                TranscriptCompleteEvent(conversation_id=self.id, transcript=self.transcript))
        if self.check_for_idle_task:
            self.logger.debug("Terminating check_for_idle Task")
            self.check_for_idle_task.cancel()
        if self.track_bot_sentiment_task:
            self.logger.debug("Terminating track_bot_sentiment Task")
            self.track_bot_sentiment_task.cancel()

        if self.post_call_callback:
            asyncio.create_task(self.post_call_callback(self))

        if self.events_manager and self.events_task:
            self.logger.debug("Terminating events Task")
            await self.events_manager.flush()
        if self.redis_event_manger and self.redis_task:
            self.logger.debug("Terminating redis events Task")
            await self.redis_event_manger.flush()
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
        self.audio_stream_handler.terminate()

    def is_active(self):
        return self.active
