from __future__ import annotations
import asyncio
import random
import threading
import typing
from copy import deepcopy
from typing import Optional, Union, TYPE_CHECKING
if TYPE_CHECKING:
    from vocode.streaming.streaming_conversation import StreamingConversation

from vocode.streaming.models.agent import (
    FollowUpAudioConfig, 
    FillerAudioConfig,
    BacktrackAudioConfig
)
from vocode.streaming.models.events import Sender
from vocode.streaming.models.transcript import (
    Message,
    Transcript,
    TranscriptCompleteEvent,
)
from vocode.streaming.synthesizer.base_synthesizer import FillerAudio
from vocode.streaming.utils.worker import InterruptibleAgentResponseWorker, InterruptibleAgentResponseEvent




class RandomResponseAudioWorker(InterruptibleAgentResponseWorker):
    """
    - Waits for a configured number of seconds and then sends random audio to the output
    - Exposes wait_for_random_audio_to_finish() which the AgentResponsesWorker waits on before
        sending responses to the output queue
    """

    name = "RandomResponse"

    def __init__(
        self,
        input_queue: asyncio.Queue[InterruptibleAgentResponseEvent[FillerAudio]],
        conversation: StreamingConversation,
        config: Union[FillerAudioConfig, FollowUpAudioConfig]
    ):
        super().__init__(input_queue=input_queue)
        self.input_queue = input_queue
        self.conversation = conversation
        self.interruptible_event_factory = self.conversation.interruptible_event_factory
        self.logger = self.conversation.logger
        self.current_filler_seconds_per_chunk: Optional[int] = None
        self.filler_audio_started_event: Optional[threading.Event] = None
        self.config = config

    async def wait_for_random_audio_to_finish(self):
        self.logger.debug(f"Waiting for {self.name} to finish")
        if (
            self.filler_audio_started_event is None
            or not self.filler_audio_started_event.set()
        ):
            self.logger.debug(
                f"Not waiting for {self.name} to finish since we didn't send any chunks"
            )
            return
        if self.interruptible_event and isinstance(
            self.interruptible_event, InterruptibleAgentResponseEvent
        ):
            await self.interruptible_event.agent_response_tracker.wait()

    def interrupt_current_random_audio(self):
        # self.logger.debug(f"Interrupting filler audio: {self.name}")
        current_event_interrupted = self.interruptible_event and self.interruptible_event.interrupt()
        self.cancel_current_task()
        return current_event_interrupted
    
    async def process(self, item: InterruptibleAgentResponseEvent[FillerAudio]):
        try:
            filler_audio = item.payload
            assert self.config is not None
            filler_synthesis_result = filler_audio.create_synthesis_result()
            self.current_filler_seconds_per_chunk = filler_audio.seconds_per_chunk
            silence_threshold = (
                self.config.silence_threshold_seconds
            )
            await asyncio.sleep(silence_threshold)
            # self.logger.debug(f"Is bot speaking: {self.conversation.is_bot_speaking}")
            # self.logger.debug(f"Is queue empty: {self.conversation.synthesis_results_queue.empty()}")
            should_send_random_audio = (
                not self.conversation.is_bot_speaking
                and self.conversation.synthesis_results_queue.empty()
            )
            self.logger.debug(f"Should send random audio: {should_send_random_audio}")
            if should_send_random_audio:
                self.logger.debug("Sending random audio to output")
                self.filler_audio_started_event = threading.Event()
                transcript_message = Message(
                    text=filler_audio.message.text,
                    sender=Sender.BOT
                )
                self.conversation.transcript.add_message(
                    message=transcript_message,
                    conversation_id=self.conversation.id
                )
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

class FillerAudioWorker(RandomResponseAudioWorker):
    name = "FillerAudio"

    def __init__(
            self,
            input_queue: asyncio.Queue,
            conversation,
            filler_audio_config: FillerAudioConfig,
    ):
        super().__init__(input_queue, conversation, filler_audio_config)

class FollowUpAudioWorker(RandomResponseAudioWorker):
    name = "FollowUpAudio"

    def __init__(
            self,
            input_queue: asyncio.Queue,
            conversation,
            follow_up_audio_config: FollowUpAudioConfig,
    ):
        super().__init__(input_queue, conversation, follow_up_audio_config)

class BacktrackAudioWorker(RandomResponseAudioWorker):
    name = "BacktrackAudio"

    def __init__(
            self,
            input_queue: asyncio.Queue,
            conversation,
            backtrack_audio_config: BacktrackAudioConfig,
    ):
        super().__init__(input_queue, conversation, backtrack_audio_config)


class RandomAudioManager:
    def __init__(self, conversation: StreamingConversation):
        self.conversation = conversation
        self.agent_config = self.conversation.agent.get_agent_config()
        self.logger = self.conversation.logger
        
        self.filler_audio_config: Optional[FillerAudioConfig] = None
        self.follow_up_audio_config: Optional[FollowUpAudioConfig] = None
        self.backtrack_audio_config: Optional[BacktrackAudioConfig] = None

        self.filler_audio_worker: Optional[FillerAudioWorker] = None
        self.follow_up_worker: Optional[FollowUpAudioWorker] = None
        self.backtrack_worker: Optional[BacktrackAudioWorker] = None

        self.filler_audio_queue: asyncio.Queue[InterruptibleAgentResponseEvent[FillerAudio]] = asyncio.Queue()
        self.follow_up_queue: asyncio.Queue[InterruptibleAgentResponseEvent[FillerAudio]] = asyncio.Queue()
        self.backtrack_queue: asyncio.Queue[InterruptibleAgentResponseEvent[FillerAudio]] = asyncio.Queue()

        if self.agent_config.send_filler_audio:
            if not isinstance(
                    self.agent_config.send_filler_audio, FillerAudioConfig
            ):
                self.filler_audio_config = FillerAudioConfig()
            else:
                self.filler_audio_config = typing.cast(
                    FillerAudioConfig, self.agent_config.send_filler_audio
                )
            self.filler_audio_worker = FillerAudioWorker(
                input_queue=self.filler_audio_queue,
                conversation=self.conversation,
                filler_audio_config=self.filler_audio_config
            )

        if self.agent_config.send_follow_up_audio:
            if not isinstance(
                    self.agent_config.send_follow_up_audio,
                    FollowUpAudioConfig,
            ):
                self.follow_up_audio_config = FollowUpAudioConfig()
            else:
                self.follow_up_audio_config = typing.cast(
                    FollowUpAudioConfig,
                    self.agent_config.send_follow_up_audio,
                )
            self.follow_up_worker = FollowUpAudioWorker(
                input_queue=self.follow_up_queue,
                conversation=self.conversation,
                follow_up_audio_config=self.follow_up_audio_config
            )
        
        if self.agent_config.send_backtrack_audio:
            if not isinstance(
                    self.agent_config.send_backtrack_audio,
                    BacktrackAudioConfig,
            ):
                self.logger.debug("Using default backtrack audio")
                self.backtrack_audio_config = BacktrackAudioConfig()
            else:
                self.backtrack_audio_config = typing.cast(
                    BacktrackAudioConfig,
                    self.agent_config.send_backtrack_audio,
                )
            self.backtrack_worker = BacktrackAudioWorker(
                input_queue=self.backtrack_queue,
                conversation=self.conversation,
                backtrack_audio_config=self.backtrack_audio_config
            )

    async def start(self):
        
        if self.filler_audio_worker is not None and self.filler_audio_config is not None:
            asyncio.create_task(
                self.conversation.synthesizer.set_filler_audios(self.filler_audio_config)
            )
            self.filler_audio_worker.start()
        if self.follow_up_worker is not None and self.follow_up_audio_config is not None:
            asyncio.create_task( 
                self.conversation.synthesizer.set_follow_up_audios(self.follow_up_audio_config)
            )
            self.follow_up_worker.start()
        if self.backtrack_worker is not None and self.backtrack_audio_config is not None:
            asyncio.create_task( 
                self.conversation.synthesizer.set_backtrack_audios(self.backtrack_audio_config)
            )
            self.backtrack_worker.start()

    async def send_filler_audio(self, agent_response_tracker: Optional[asyncio.Event]):
        self.stop_all_audios()
        if self.filler_audio_worker is None:
            return
        self.logger.debug("Sending filler audio")
        assert self.filler_audio_worker is not None
        filler_audios = self.conversation.synthesizer.filler_audios
        last_user_message = self.conversation.transcript.get_last_user_message()[1]
        if filler_audios:
            if (
                '?' in last_user_message and
                not self.conversation.is_interrupted
            ):
                filler_audio = random.choice(
                    filler_audios['question']
                )
                self.logger.debug(f"Chose question type, text: {filler_audio.message.text}")

            elif not self.conversation.is_interrupted:
                filler_audio = random.choice(
                    filler_audios['confirm']
                )
                self.logger.debug(f"Chose confirmation type, text: {filler_audio.message.text}")

            elif self.conversation.is_interrupted:
                filler_audio = random.choice(
                    filler_audios['interrupt']
                )
                self.logger.debug(f"Chose confirmation type, text: {filler_audio.message.text}")

            event = self.conversation.interruptible_event_factory.create_interruptible_agent_response_event(
                    filler_audio,
                    is_interruptible=filler_audio.is_interruptible,
                    agent_response_tracker=agent_response_tracker,
                )
            self.filler_audio_worker.consume_nonblocking(event)
        else:
            self.logger.debug(
                "No filler audio available for synthesizer"
            )

    async def send_follow_up_audio(self, agent_response_tracker: Optional[asyncio.Event]):
        if self.follow_up_worker is None:
            return
        self.logger.debug("Sending follow up audio")
        assert self.follow_up_worker is not None
        follow_up_audios = self.conversation.synthesizer.follow_up_audios
        if follow_up_audios:
            follow_up_audio: FillerAudio = random.choice(follow_up_audios)
            self.logger.debug(f"Chose follow up audio, {follow_up_audio.message.text}")
            event = self.conversation.interruptible_event_factory.create_interruptible_agent_response_event(
                follow_up_audio,
                is_interruptible=follow_up_audio.is_interruptible,
                agent_response_tracker=agent_response_tracker,
            )
            self.follow_up_worker.consume_nonblocking(event)
        else:
            self.logger.debug("No follow up audio available")
    
    async def send_backtrack_audio(self, agent_response_tracker: Optional[asyncio.Event]):
        self.stop_all_audios()
        if self.backtrack_worker is None:
            return
        self.logger.debug("Sending backtrack audio")
        assert self.backtrack_worker is not None
        backtrack_audios = self.conversation.synthesizer.backtrack_audios
        if backtrack_audios:
            backtrack_audio: FillerAudio = random.choice(backtrack_audios)
            self.logger.debug(f"Chose backtrack audio, {backtrack_audio.message.text}")
            event = self.conversation.interruptible_event_factory.create_interruptible_agent_response_event(
                backtrack_audio,
                is_interruptible=backtrack_audio.is_interruptible,
                agent_response_tracker=agent_response_tracker,
            )
            self.backtrack_worker.consume_nonblocking(event)
        else:
            self.logger.debug("No backtrack audio available")

    async def stop_filler_audio(self):
        if self.filler_audio_worker:
            if self.filler_audio_worker.interrupt_current_random_audio():
                await self.filler_audio_worker.wait_for_random_audio_to_finish()

    async def stop_follow_up_audio(self):
        if self.follow_up_worker:
            if self.follow_up_worker.interrupt_current_random_audio():
                await self.follow_up_worker.wait_for_random_audio_to_finish()
    
    async def stop_backtrack_audio(self):
        if self.backtrack_worker:
            if self.backtrack_worker.interrupt_current_random_audio():
                await self.backtrack_worker.wait_for_random_audio_to_finish()

    def terminate(self):
        if self.filler_audio_worker is not None:
            self.logger.debug("Terminating filler audio worker")
            self.filler_audio_worker.terminate()
        if self.follow_up_worker is not None:
            self.logger.debug("Terminating follow up worker")
            self.follow_up_worker.terminate()
        if self.backtrack_worker is not None:
            self.logger.debug("Terminating backtrack worker")
            self.backtrack_worker.terminate()

    def sync_stop_follow_up_audio(self):
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self.stop_follow_up_audio())
        except Exception as e:
            self.logger.debug(f"Exception while stopping follow up audio: {repr(e)}")

    def stop_all_audios(self):
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self.stop_follow_up_audio())
            loop.create_task(self.stop_filler_audio())
            loop.create_task(self.stop_backtrack_audio())
        except Exception as e:
            self.logger.debug(f"Exception while stopping all audios: {repr(e)}")

    def sync_send_filler_audio(self, agent_response_tracker: Optional[asyncio.Event]):
        loop = asyncio.get_event_loop()
        loop.create_task(self.send_filler_audio(agent_response_tracker))

    def sync_send_follow_up_audio(self, agent_response_tracker: Optional[asyncio.Event]):
        loop = asyncio.get_event_loop()
        loop.create_task(self.send_follow_up_audio(agent_response_tracker))

    def sync_send_backtrack_audio(self, agent_response_tracker: Optional[asyncio.Event]):
        loop = asyncio.get_event_loop()
        loop.create_task(self.send_backtrack_audio(agent_response_tracker))