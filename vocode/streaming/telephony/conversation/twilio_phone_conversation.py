import asyncio
import base64
import json
import os
import threading
from enum import Enum
from typing import AsyncGenerator, Optional

from fastapi import WebSocket
from loguru import logger

from vocode.streaming.agent.abstract_factory import AbstractAgentFactory
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.events import PhoneCallConnectedEvent
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.models.telephony import PhoneCallDirection, TwilioConfig
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.models.transcript import Message
from vocode.streaming.output_device.twilio_output_device import TwilioOutputDevice
from vocode.streaming.synthesizer.abstract_factory import AbstractSynthesizerFactory
from vocode.streaming.synthesizer.base_synthesizer import SynthesisResult
from vocode.streaming.synthesizer.input_streaming_synthesizer import InputStreamingSynthesizer
from vocode.streaming.telephony.client.twilio_client import TwilioClient
from vocode.streaming.telephony.config_manager.base_config_manager import BaseConfigManager
from vocode.streaming.telephony.conversation.abstract_phone_conversation import (
    AbstractPhoneConversation,
)
from vocode.streaming.telephony.conversation.mark_message_queue import (
    ChunkFinishedMarkMessage,
    MarkMessage,
    MarkMessageQueue,
    UtteranceFinishedMarkMessage,
)
from vocode.streaming.transcriber.abstract_factory import AbstractTranscriberFactory
from vocode.streaming.utils import create_utterance_id
from vocode.streaming.utils.create_task import asyncio_create_task_with_done_error_log
from vocode.streaming.utils.events_manager import EventsManager
from vocode.streaming.utils.state_manager import TwilioPhoneConversationStateManager


class TwilioPhoneConversationWebsocketAction(Enum):
    CLOSE_WEBSOCKET = 1


class TwilioPhoneConversation(AbstractPhoneConversation[TwilioOutputDevice]):
    telephony_provider = "twilio"

    def __init__(
        self,
        direction: PhoneCallDirection,
        from_phone: str,
        to_phone: str,
        base_url: str,
        config_manager: BaseConfigManager,
        agent_config: AgentConfig,
        transcriber_config: TranscriberConfig,
        synthesizer_config: SynthesizerConfig,
        twilio_sid: str,
        agent_factory: AbstractAgentFactory,
        transcriber_factory: AbstractTranscriberFactory,
        synthesizer_factory: AbstractSynthesizerFactory,
        twilio_config: Optional[TwilioConfig] = None,
        conversation_id: Optional[str] = None,
        events_manager: Optional[EventsManager] = None,
        record_call: bool = False,
        speed_coefficient: float = 1.0,
        noise_suppression: bool = False,  # is currently a no-op
    ):
        super().__init__(
            direction=direction,
            from_phone=from_phone,
            to_phone=to_phone,
            base_url=base_url,
            config_manager=config_manager,
            output_device=TwilioOutputDevice(),
            agent_config=agent_config,
            transcriber_config=transcriber_config,
            synthesizer_config=synthesizer_config,
            conversation_id=conversation_id,
            events_manager=events_manager,
            transcriber_factory=transcriber_factory,
            agent_factory=agent_factory,
            synthesizer_factory=synthesizer_factory,
            speed_coefficient=speed_coefficient,
        )
        self.mark_message_queue: MarkMessageQueue = MarkMessageQueue()
        self.config_manager = config_manager
        self.twilio_config = twilio_config or TwilioConfig(
            account_sid=os.environ["TWILIO_ACCOUNT_SID"],
            auth_token=os.environ["TWILIO_AUTH_TOKEN"],
        )
        self.telephony_client = TwilioClient(
            base_url=self.base_url, maybe_twilio_config=self.twilio_config
        )
        self.twilio_sid = twilio_sid
        self.record_call = record_call

    def create_state_manager(self) -> TwilioPhoneConversationStateManager:
        return TwilioPhoneConversationStateManager(self)

    async def attach_ws_and_start(self, ws: WebSocket):
        super().attach_ws(ws)

        await self._wait_for_twilio_start(ws)
        await self.start()
        self.events_manager.publish_event(
            PhoneCallConnectedEvent(
                conversation_id=self.id,
                to_phone_number=self.to_phone,
                from_phone_number=self.from_phone,
            )
        )
        while self.active:
            message = await ws.receive_text()
            response = await self._handle_ws_message(message)
            if response == TwilioPhoneConversationWebsocketAction.CLOSE_WEBSOCKET:
                break
        await ws.close(code=1000, reason=None)
        await self.terminate()

    async def _wait_for_twilio_start(self, ws: WebSocket):
        assert isinstance(self.output_device, TwilioOutputDevice)
        while True:
            message = await ws.receive_text()
            if not message:
                continue
            data = json.loads(message)
            if data["event"] == "start":
                logger.debug(f"Media WS: Received event '{data['event']}': {message}")
                self.output_device.stream_sid = data["start"]["streamSid"]
                break

    async def _handle_ws_message(self, message) -> Optional[TwilioPhoneConversationWebsocketAction]:
        if message is None:
            return TwilioPhoneConversationWebsocketAction.CLOSE_WEBSOCKET

        data = json.loads(message)
        if data["event"] == "media":
            media = data["media"]
            chunk = base64.b64decode(media["payload"])
            self.receive_audio(chunk)
        if data["event"] == "mark":
            mark_name = data["mark"]["name"]
            if mark_name.startswith("chunk-"):
                utterance_id, chunk_idx = mark_name.split("-")[1:]
                self.mark_message_queue.put_nowait(
                    utterance_id=utterance_id,
                    mark_message=ChunkFinishedMarkMessage(chunk_idx=int(chunk_idx)),
                )
            elif mark_name.startswith("utterance"):
                utterance_id = mark_name.split("-")[1]
                self.mark_message_queue.put_nowait(
                    utterance_id=utterance_id,
                    mark_message=UtteranceFinishedMarkMessage(),
                )
        elif data["event"] == "stop":
            logger.debug(f"Media WS: Received event 'stop': {message}")
            logger.debug("Stopping...")
            return TwilioPhoneConversationWebsocketAction.CLOSE_WEBSOCKET
        return None

    async def _send_chunks(
        self,
        utterance_id: str,
        chunk_generator: AsyncGenerator[SynthesisResult.ChunkResult, None],
        clear_message_lock: asyncio.Lock,
        stop_event: threading.Event,
    ):
        chunk_idx = 0
        try:
            async for chunk_result in chunk_generator:
                async with clear_message_lock:
                    if stop_event.is_set():
                        break
                    self.output_device.consume_nonblocking(chunk_result.chunk)
                    self.output_device.send_chunk_finished_mark(utterance_id, chunk_idx)
                    chunk_idx += 1
        except asyncio.CancelledError:
            pass
        finally:
            logger.debug("Finished sending all chunks to Twilio")
            self.output_device.send_utterance_finished_mark(utterance_id)

    async def send_speech_to_output(
        self,
        message: str,
        synthesis_result: SynthesisResult,
        stop_event: threading.Event,
        seconds_per_chunk: float,
        transcript_message: Optional[Message] = None,
        started_event: Optional[threading.Event] = None,
    ):
        """In contrast with send_speech_to_output in the base class, this function uses mark messages
        to support interruption - we send all chunks to the output device, and then wait for mark messages[0]
        that indicate that each chunk has been played. This means that we don't need to depends on asyncio.sleep
        to support interruptions.

        Once we receive an interruption signal:
        - we send a clear message to Twilio to stop playing all queued audio
        - based on the number of mark messages we've received back, we know how many chunks were played and can indicate on the transcript

        [0] https://www.twilio.com/docs/voice/twiml/stream#websocket-messages-to-twilio
        """

        if self.transcriber.get_transcriber_config().mute_during_speech:
            logger.debug("Muting transcriber")
            self.transcriber.mute()
        message_sent = message
        cut_off = False
        chunk_idx = 0
        seconds_spoken = 0.0
        logger.debug(f"Start sending speech {message} to output")

        utterance_id = create_utterance_id()
        self.mark_message_queue.create_utterance_queue(utterance_id)

        first_chunk_span = self._maybe_create_first_chunk_span(synthesis_result, message)

        clear_message_lock = asyncio.Lock()

        asyncio_create_task_with_done_error_log(
            self._send_chunks(
                utterance_id,
                synthesis_result.chunk_generator,
                clear_message_lock,
                stop_event,
            ),
        )
        mark_event: MarkMessage
        first = True
        while True:
            mark_event = await self.mark_message_queue.get(utterance_id)
            if isinstance(mark_event, UtteranceFinishedMarkMessage):
                break
            if first and first_chunk_span:
                self._track_first_chunk(first_chunk_span, synthesis_result)
            first = False
            seconds_spoken = mark_event.chunk_idx * seconds_per_chunk
            # Lock here so that we check the stop event and send the clear message atomically
            # w.r.t. the _send_chunks task which also checks the stop event
            # Otherwise, we could send the clear message while _send_chunks is in the middle of sending a chunk
            # and the synthesis wouldn't be cleared
            async with clear_message_lock:
                if stop_event.is_set():
                    self.output_device.send_clear_message()
                    logger.debug(
                        "Interrupted, stopping text to speech after {} chunks".format(chunk_idx)
                    )
                    message_sent = synthesis_result.get_message_up_to(seconds_spoken)
                    cut_off = True
                    break
            if chunk_idx == 0:
                if started_event:
                    started_event.set()
            self.mark_last_action_timestamp()
            chunk_idx += 1
            seconds_spoken += seconds_per_chunk
            if transcript_message:
                transcript_message.text = synthesis_result.get_message_up_to(seconds_spoken)
        self.mark_message_queue.delete_utterance_queue(utterance_id)
        if self.transcriber.get_transcriber_config().mute_during_speech:
            logger.debug("Unmuting transcriber")
            self.transcriber.unmute()
        if transcript_message:
            # For input streaming synthesizers, we have to buffer the message as it is streamed in
            # What is said is federated fully by synthesis_result.get_message_up_to
            if isinstance(self.synthesizer, InputStreamingSynthesizer):
                message_sent = transcript_message.text
            else:
                transcript_message.text = message_sent
            transcript_message.is_final = not cut_off
        if synthesis_result.synthesis_total_span:
            synthesis_result.synthesis_total_span.finish()
        return message_sent, cut_off
