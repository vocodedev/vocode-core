import asyncio
import random
import threading
import typing
from typing import Optional

from vocode.streaming.models.agent import FollowUpAudioConfig, FillerAudioConfig, BackTrackingConfig, \
    RandomResponseAudioConfig
from vocode.streaming.synthesizer.base_synthesizer import FillerAudio
from vocode.streaming.utils.worker import InterruptableAgentResponseWorker, InterruptableAgentResponseEvent


class RandomResponseAudioWorker(InterruptableAgentResponseWorker):
    """
    - Waits for a configured number of seconds and then sends filler audio to the output
    - Exposes wait_for_filler_audio_to_finish() which the AgentResponsesWorker waits on before
      sending responses to the output queue
    """
    name = "RandomResponse"

    def __init__(
            self,
            input_queue: asyncio.Queue[InterruptableAgentResponseEvent[FillerAudio]],
            conversation,
            config: RandomResponseAudioConfig,
    ):
        super().__init__(input_queue=input_queue)
        self.input_queue = input_queue
        self.conversation = conversation
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
        if self.interruptable_event and isinstance(
                self.interruptable_event, InterruptableAgentResponseEvent
        ):
            await self.interruptable_event.agent_response_tracker.wait()

    def interrupt_current_filler_audio(self):
        self.logger.debug(f"Interrupting {self.name}")
        return self.interruptable_event and self.interruptable_event.interrupt()

    async def process(self, item: InterruptableAgentResponseEvent[FillerAudio]):
        try:
            filler_audio = item.payload
            assert self.config is not None
            filler_synthesis_result = filler_audio.create_synthesis_result()
            self.current_filler_seconds_per_chunk = filler_audio.seconds_per_chunk
            silence_threshold = (
                self.config.silence_threshold_seconds
            )
            await asyncio.sleep(silence_threshold)
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


class FillerAudioWorker(RandomResponseAudioWorker):
    name = "FillerAudio"

    def __init__(
            self,
            input_queue: asyncio.Queue[InterruptableAgentResponseEvent[FillerAudio]],
            conversation,
            filler_audio_config: FillerAudioConfig,
    ):
        super().__init__(input_queue, conversation, filler_audio_config)


class BackTrackingWorker(RandomResponseAudioWorker):
    name = "BackTracking"

    def __init__(
            self,
            input_queue: asyncio.Queue[InterruptableAgentResponseEvent[FillerAudio]],
            conversation,
            back_tracking_config: BackTrackingConfig,
    ):
        super().__init__(input_queue, conversation, back_tracking_config)


class FollowUpAudioWorker(RandomResponseAudioWorker):
    name = "FollowUpAudio"

    def __init__(
            self,
            input_queue: asyncio.Queue[InterruptableAgentResponseEvent[FillerAudio]],
            conversation,
            follow_up_audio_config: FollowUpAudioConfig,
    ):
        super().__init__(input_queue, conversation, follow_up_audio_config)


class RandomAudioManager:
    def __init__(self, conversation):
        self.conversation = conversation
        self.agent_config = self.conversation.agent.get_agent_config()
        self.logger = self.conversation.logger
        self.back_tracking_config: Optional[BackTrackingConfig] = None
        self.filler_audio_config: Optional[FillerAudioConfig] = None
        self.follow_up_audio_config: Optional[FollowUpAudioConfig] = None
        self.filler_audio_worker = None
        self.back_tracking_worker = None
        self.follow_up_worker = None

        self.filler_audio_queue: asyncio.Queue[InterruptableAgentResponseEvent[FillerAudio]] = asyncio.Queue()
        self.back_tracking_audio_queue: asyncio.Queue[InterruptableAgentResponseEvent[FillerAudio]] = asyncio.Queue()
        self.follow_up_queue: asyncio.Queue[InterruptableAgentResponseEvent[FillerAudio]] = asyncio.Queue()

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

        if self.agent_config.send_back_tracking_audio:
            if not isinstance(
                    self.agent_config.send_back_tracking_audio,
                    BackTrackingConfig,
            ):
                self.back_tracking_config = BackTrackingConfig()
            else:
                self.back_tracking_config = typing.cast(
                    BackTrackingConfig,
                    self.agent_config.send_back_tracking_audio,
                )
            self.back_tracking_worker = BackTrackingWorker(
                input_queue=self.back_tracking_audio_queue,
                conversation=self.conversation,
                back_tracking_config=self.back_tracking_config
            )

    async def start(self):
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
        if self.filler_audio_worker is not None and self.filler_audio_config is not None:
            await self.conversation.synthesizer.set_filler_audios(self.filler_audio_config)
            self.filler_audio_worker.start()
        if self.back_tracking_worker is not None and self.back_tracking_config is not None:
            await self.conversation.synthesizer.set_back_tracking_audios(self.back_tracking_config)
            self.back_tracking_worker.start()
        if self.follow_up_worker is not None and self.follow_up_audio_config is not None:
            await self.conversation.synthesizer.set_follow_up_audios(self.follow_up_audio_config)
            self.follow_up_worker.start()

    async def send_back_tracking_audio(self, agent_response_tracker: Optional[asyncio.Event]):
        await self.stop_all_audios()
        if self.back_tracking_worker is None:
            return
        self.logger.debug("Sending back tracking audio")
        assert self.back_tracking_worker is not None
        if self.conversation.synthesizer.back_tracking_audios:
            back_tracking_audio = random.choice(
                self.conversation.synthesizer.back_tracking_audios
            )
            self.logger.debug(f"Chose {back_tracking_audio.message.text} for back tracking")
            event = self.conversation.interruptable_event_factory.create_interruptable_agent_response_event(
                back_tracking_audio,
                is_interruptable=back_tracking_audio.is_interruptable,
                agent_response_tracker=agent_response_tracker,
            )
            self.back_tracking_worker.consume_nonblocking(event)
        else:
            self.logger.debug("No back tracking audio available")

    async def send_filler_audio(self, agent_response_tracker: Optional[asyncio.Event]):
        await self.stop_all_audios()
        if self.filler_audio_worker is None:
            return
        self.logger.debug("Sending filler audio")
        assert self.filler_audio_worker is not None
        if self.conversation.synthesizer.filler_audios:
            filler_audio: Optional[FillerAudio] = None
            if '?' in self.conversation.transcript.get_last_user_message()[-1] and \
                    not self.conversation.is_interrupted:
                filler_audio = random.choice(
                    self.conversation.synthesizer.filler_audios['QUESTIONS']
                )
                self.logger.debug(f"Chose question type, text: {filler_audio.message.text}")

            elif not self.conversation.is_interrupted:
                filler_audio = random.choice(
                    self.conversation.synthesizer.filler_audios['AFFIRMATIONS']
                )
                self.logger.debug(f"Chose confirmation type, text: {filler_audio.message.text}")

            elif self.conversation.is_interrupted:
                filler_audio = random.choice(
                    self.conversation.synthesizer.filler_audios['INTERRUPTIONS']
                )
                self.logger.debug(f"Chose interruption type, text: {filler_audio.message.text}")

            event = self.conversation.interruptable_event_factory.create_interruptable_agent_response_event(
                filler_audio,
                is_interruptable=filler_audio.is_interruptable,
                agent_response_tracker=agent_response_tracker,
            )
            self.filler_audio_worker.consume_nonblocking(event)
        else:
            self.logger.debug(
                "No filler audio available for synthesizer"
            )

    async def send_follow_up_audio(self, agent_response_tracker: Optional[asyncio.Event]):
        await self.stop_all_audios()
        if self.follow_up_worker is None:
            return
        self.logger.debug("Sending follow up audio")
        assert self.follow_up_worker is not None
        if self.conversation.synthesizer.follow_up_audios:
            follow_up_audio = random.choice(
                self.conversation.synthesizer.follow_up_audios
            )
            self.logger.debug(f"Chose follow up audio, {follow_up_audio.message.text}")
            event = self.conversation.interruptable_event_factory.create_interruptable_agent_response_event(
                follow_up_audio,
                is_interruptable=follow_up_audio.is_interruptable,
                agent_response_tracker=agent_response_tracker,
            )
            self.follow_up_worker.consume_nonblocking(event)
        else:
            self.logger.debug("No follow up audio available")

    async def stop_filler_audio(self):
        if self.filler_audio_worker:
            if self.filler_audio_worker.interrupt_current_filler_audio():
                await self.filler_audio_worker.wait_for_random_audio_to_finish()

    async def stop_back_tracking_audio(self):
        if self.back_tracking_worker:
            if self.back_tracking_worker.interrupt_current_filler_audio():
                await self.back_tracking_worker.wait_for_random_audio_to_finish()

    async def stop_follow_up_audio(self):
        if self.follow_up_worker:
            if self.follow_up_worker.interrupt_current_filler_audio():
                await self.follow_up_worker.wait_for_random_audio_to_finish()

    def terminate(self):
        if self.filler_audio_worker is not None:
            self.logger.debug("Terminating filler audio worker")
            self.filler_audio_worker.terminate()
        if self.back_tracking_config is not None:
            self.logger.debug("Terminating back tracking worker")
            self.back_tracking_worker.terminate()
        if self.follow_up_worker is not None:
            self.logger.debug("Terminating follow up worker")
            self.follow_up_worker.terminate()

    async def stop_all_audios(self):
        await self.stop_follow_up_audio()
        await self.stop_back_tracking_audio()
        await self.stop_filler_audio()
