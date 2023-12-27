import asyncio
from fastapi import WebSocket
import base64
from enum import Enum
import json
import logging
from typing import Optional, Tuple
from vocode import getenv
from vocode.streaming.agent.factory import AgentFactory
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.events import PhoneCallConnectedEvent

from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.output_device.twilio_output_device import TwilioOutputDevice
from vocode.streaming.models.synthesizer import (
    SynthesizerConfig,
)
from vocode.streaming.models.transcriber import (
    TranscriberConfig,
)
from vocode.streaming.synthesizer.factory import SynthesizerFactory
from vocode.streaming.telephony.client.twilio_client import TwilioClient
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)
from vocode.streaming.telephony.conversation.call import Call
from vocode.streaming.transcriber.factory import TranscriberFactory
from vocode.streaming.utils.events_manager import EventsManager
from vocode.streaming.utils.state_manager import TwilioCallStateManager
from vocode.streaming.utils.cache import RedisRenewableTTLCache


TWILIO_CHUNK_DURATION_MS = 20

BUFFER_DURATION_MS = 60
# each twilio chunk is 20ms at 8000Hz with 8 bits (1 byte) per sample: 160 bytes
TWILIO_BYTES_PER_CHUNK = 160
BUFFER_SIZE = int(BUFFER_DURATION_MS/TWILIO_CHUNK_DURATION_MS) * 160

class PhoneCallWebsocketAction(Enum):
    CLOSE_WEBSOCKET = 1


class TwilioCall(Call[TwilioOutputDevice]):
    def __init__(
        self,
        from_phone: str,
        to_phone: str,
        base_url: str,
        config_manager: BaseConfigManager,
        agent_config: AgentConfig,
        transcriber_config: TranscriberConfig,
        synthesizer_config: SynthesizerConfig,
        twilio_sid: str,
        twilio_config: Optional[TwilioConfig] = None,
        conversation_id: Optional[str] = None,
        transcriber_factory: TranscriberFactory = TranscriberFactory(),
        agent_factory: AgentFactory = AgentFactory(),
        synthesizer_factory: SynthesizerFactory = SynthesizerFactory(),
        synthesizer_cache: Optional[RedisRenewableTTLCache] = None,
        events_manager: Optional[EventsManager] = None,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(
            from_phone,
            to_phone,
            base_url,
            config_manager,
            TwilioOutputDevice(),
            agent_config,
            transcriber_config,
            synthesizer_config,
            conversation_id=conversation_id,
            events_manager=events_manager,
            transcriber_factory=transcriber_factory,
            agent_factory=agent_factory,
            synthesizer_factory=synthesizer_factory,
            synthesizer_cache=synthesizer_cache,
            logger=logger,
        )
        self.base_url = base_url
        self.config_manager = config_manager
        self.twilio_config = twilio_config or TwilioConfig(
            account_sid=getenv("TWILIO_ACCOUNT_SID"),
            auth_token=getenv("TWILIO_AUTH_TOKEN"),
        )
        self.telephony_client = TwilioClient(
            base_url=base_url, twilio_config=self.twilio_config
        )
        self.twilio_sid = twilio_sid
        self.latest_media_timestamp = 0

    def create_state_manager(self) -> TwilioCallStateManager:
        return TwilioCallStateManager(self)

    async def attach_ws_and_start(self, ws: WebSocket):
        super().attach_ws(ws)

        twilio_call_ref = self.telephony_client.twilio_client.calls(self.twilio_sid)
        twilio_call = twilio_call_ref.fetch()

        if self.twilio_config.record:
            recordings_create_params = (
                self.twilio_config.extra_params.get("recordings_create_params")
                if self.twilio_config.extra_params
                else None
            )
            recording = (
                twilio_call_ref.recordings.create(**recordings_create_params)
                if recordings_create_params
                else twilio_call_ref.recordings.create()
            )
            self.logger.info(f"Recording: {recording.sid}")

        # since now AMD is async, twilio_call should not contain the answered_by field
        if twilio_call.answered_by in ("machine_start", "fax"): 
            self.logger.info(f"Call answered by {twilio_call.answered_by}")          
            twilio_call.update(status="completed")
        else:
            await self.wait_for_twilio_start(ws)
            self.events_manager.publish_event(
                PhoneCallConnectedEvent(
                    conversation_id=self.id,
                    to_phone_number=self.to_phone,
                    from_phone_number=self.from_phone,
                )
            )
            # await super().start()
            started_event = asyncio.Event()
            start_conversation_task = asyncio.create_task(
                super().start(started_event=started_event)
            )
            self.logger.debug("Started Streaming Conversation...")
            
            await started_event.wait()
            self.logger.debug("Started event set!")
            twilio_buffer = bytearray(b"")
            twilio_audio_time_ms: float = 0.0
            new_twilio_audio_time_ms: float = 0.0
            interval_to_log_ms = 3000
            while self.active:
                message = await ws.receive_text()
                response, new_twilio_audio_time_ms = await self.handle_ws_message(message, twilio_buffer, twilio_audio_time_ms)
                if (int(twilio_audio_time_ms) // interval_to_log_ms) != (int(new_twilio_audio_time_ms) // interval_to_log_ms):
                    self.logger.debug(f"Received {new_twilio_audio_time_ms/1000} seconds of Twilio audio.")   
                twilio_audio_time_ms = new_twilio_audio_time_ms
                if response == PhoneCallWebsocketAction.CLOSE_WEBSOCKET:
                    break
            if not start_conversation_task.done():
                await start_conversation_task

        await self.config_manager.delete_config(self.id)
        await self.tear_down()

    async def wait_for_twilio_start(self, ws: WebSocket):
        assert isinstance(self.output_device, TwilioOutputDevice)
        while True:
            message = await ws.receive_text()
            if not message:
                continue
            data = json.loads(message)
            if data["event"] == "start":
                self.logger.debug(
                    f"Media WS: Received event '{data['event']}': {message}"
                )
                self.output_device.stream_sid = data["start"]["streamSid"]
                break

    async def handle_ws_message(
            self, 
            message,
            twilio_buffer: bytearray,
            twilio_audio_time_ms: float
        ) -> Tuple[Optional[PhoneCallWebsocketAction], float]:
        if message is None:
            return PhoneCallWebsocketAction.CLOSE_WEBSOCKET, twilio_audio_time_ms

        # check https://github.com/deepgram-devs/deepgram-twilio-streaming-python/blob/master/twilio.py        
        data = json.loads(message)
        if data["event"] == "media":
            media = data["media"]
            chunk = base64.b64decode(media["payload"])
            ms_to_fill = int(media["timestamp"]) - (self.latest_media_timestamp + TWILIO_CHUNK_DURATION_MS)
            if ms_to_fill > 0:
                bytes_to_fill = 8 * ms_to_fill
                # NOTE: 0xff is silence for mulaw audio
                # and there are 8 bytes per ms of data for our format (8 bit, 8000 Hz)
                # self.receive_audio(b"\xff" * bytes_to_fill)
                # self.logger.debug(f"Filling {bytes_to_fill} bytes of silence")
                twilio_buffer.extend(b"\xff" * bytes_to_fill)
                twilio_audio_time_ms += ms_to_fill
            self.latest_media_timestamp = int(media["timestamp"])
            twilio_buffer.extend(chunk)
            twilio_audio_time_ms += TWILIO_CHUNK_DURATION_MS
            # self.receive_audio(chunk)

            while len(twilio_buffer) >= BUFFER_SIZE:
                self.receive_audio(bytes(twilio_buffer[:BUFFER_SIZE]))
                twilio_buffer[:] = twilio_buffer[BUFFER_SIZE:]

        elif data["event"] == "stop":
            self.logger.debug(f"Media WS: Received event 'stop': {message}")
            self.logger.debug("Stopping...")
            return PhoneCallWebsocketAction.CLOSE_WEBSOCKET, twilio_audio_time_ms
        return None, twilio_audio_time_ms
