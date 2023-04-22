from fastapi import WebSocket
import base64
from enum import Enum
import json
import logging
from typing import Optional
from vocode import getenv
from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.agent.factory import AgentFactory
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.events import PhoneCallConnectedEvent, PhoneCallEndedEvent

from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.streaming.models.telephony import CallConfig, TwilioConfig
from vocode.streaming.output_device.twilio_output_device import TwilioOutputDevice
from vocode.streaming.models.synthesizer import (
    AzureSynthesizerConfig,
    SynthesizerConfig,
)
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
    TranscriberConfig,
)
from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer
from vocode.streaming.synthesizer.factory import SynthesizerFactory
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)
from vocode.streaming.telephony.constants import DEFAULT_SAMPLING_RATE
from vocode.streaming.telephony.twilio import create_twilio_client, end_twilio_call
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.streaming.transcriber.base_transcriber import BaseTranscriber
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber
from vocode.streaming.transcriber.factory import TranscriberFactory
from vocode.streaming.utils.events_manager import EventsManager


class PhoneCallAction(Enum):
    CLOSE_WEBSOCKET = 1


class Call(StreamingConversation):
    def __init__(
        self,
        base_url: str,
        config_manager: BaseConfigManager,
        agent_config: AgentConfig,
        transcriber_config: TranscriberConfig,
        synthesizer_config: SynthesizerConfig,
        twilio_config: Optional[TwilioConfig] = None,
        twilio_sid: Optional[str] = None,
        conversation_id: Optional[str] = None,
        transcriber_factory: TranscriberFactory = TranscriberFactory(),
        agent_factory: AgentFactory = AgentFactory(),
        synthesizer_factory: SynthesizerFactory = SynthesizerFactory(),
        events_manager: Optional[EventsManager] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.base_url = base_url
        self.config_manager = config_manager
        self.output_device = TwilioOutputDevice()
        self.twilio_config = twilio_config or TwilioConfig(
            account_sid=getenv("TWILIO_ACCOUNT_SID"),
            auth_token=getenv("TWILIO_AUTH_TOKEN"),
        )
        self.twilio_client = create_twilio_client(twilio_config)
        super().__init__(
            self.output_device,
            transcriber_factory.create_transcriber(transcriber_config),
            agent_factory.create_agent(agent_config),
            synthesizer_factory.create_synthesizer(synthesizer_config),
            conversation_id=conversation_id,
            per_chunk_allowance_seconds=0.01,
            events_manager=events_manager,
            logger=logger,
        )
        self.twilio_sid = twilio_sid
        self.latest_media_timestamp = 0

    @staticmethod
    def from_call_config(
        base_url: str,
        call_config: CallConfig,
        config_manager: BaseConfigManager,
        conversation_id: str,
        logger: logging.Logger,
        transcriber_factory: TranscriberFactory = TranscriberFactory(),
        agent_factory: AgentFactory = AgentFactory(),
        synthesizer_factory: SynthesizerFactory = SynthesizerFactory(),
        events_manager: Optional[EventsManager] = None,
    ):
        return Call(
            base_url=base_url,
            logger=logger,
            config_manager=config_manager,
            agent_config=call_config.agent_config,
            transcriber_config=call_config.transcriber_config,
            synthesizer_config=call_config.synthesizer_config,
            twilio_config=call_config.twilio_config,
            twilio_sid=call_config.twilio_sid,
            conversation_id=conversation_id,
            transcriber_factory=transcriber_factory,
            agent_factory=agent_factory,
            synthesizer_factory=synthesizer_factory,
            events_manager=events_manager,
        )

    async def attach_ws_and_start(self, ws: WebSocket):
        self.logger.debug("Trying to attach WS to outbound call")
        self.output_device.ws = ws
        self.logger.debug("Attached WS to outbound call")

        twilio_call = self.twilio_client.calls(self.twilio_sid).fetch()

        if twilio_call.answered_by in ("machine_start", "fax"):
            self.logger.info(f"Call answered by {twilio_call.answered_by}")
            twilio_call.update(status="completed")
        else:
            await self.wait_for_twilio_start(ws)
            await super().start()
            self.events_manager.publish_event(
                PhoneCallConnectedEvent(conversation_id=self.id)
            )
            while self.active:
                message = await ws.receive_text()
                response = await self.handle_ws_message(message)
                if response == PhoneCallAction.CLOSE_WEBSOCKET:
                    break
        self.tear_down()

    async def wait_for_twilio_start(self, ws: WebSocket):
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

    async def handle_ws_message(self, message) -> PhoneCallAction:
        if message is None:
            return PhoneCallAction.CLOSE_WEBSOCKET

        data = json.loads(message)
        if data["event"] == "media":
            media = data["media"]
            chunk = base64.b64decode(media["payload"])
            if self.latest_media_timestamp + 20 < int(media["timestamp"]):
                bytes_to_fill = 8 * (
                    int(media["timestamp"]) - (self.latest_media_timestamp + 20)
                )
                self.logger.debug(f"Filling {bytes_to_fill} bytes of silence")
                # NOTE: 0xff is silence for mulaw audio
                self.receive_audio(b"\xff" * bytes_to_fill)
            self.latest_media_timestamp = int(media["timestamp"])
            self.receive_audio(chunk)
        elif data["event"] == "stop":
            self.logger.debug(f"Media WS: Received event 'stop': {message}")
            self.logger.debug("Stopping...")
            return PhoneCallAction.CLOSE_WEBSOCKET

    def mark_terminated(self):
        super().mark_terminated()
        end_twilio_call(
            self.twilio_client,
            self.twilio_sid,
        )
        self.config_manager.delete_config(self.id)

    def tear_down(self):
        self.events_manager.publish_event(
            PhoneCallEndedEvent(conversation_id=self.id)
        )
        self.terminate()
