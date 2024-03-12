import base64
import json
import logging
from enum import Enum
from typing import Optional

from fastapi import WebSocket

from vocode import getenv
from vocode.streaming.agent.factory import AgentFactory
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.events import PhoneCallConnectedEvent
from vocode.streaming.models.synthesizer import (
    SynthesizerConfig,
)
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.models.transcriber import (
    TranscriberConfig,
)
from vocode.streaming.output_device.twilio_output_device import TwilioOutputDevice
from vocode.streaming.synthesizer.factory import SynthesizerFactory
from vocode.streaming.telephony.client.twilio_client import TwilioClient
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)
from vocode.streaming.telephony.conversation.call import Call
from vocode.streaming.transcriber.factory import TranscriberFactory
from vocode.streaming.utils.events_manager import EventsManager
from vocode.streaming.utils.state_manager import TwilioCallStateManager


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
            conversation_id=twilio_sid,
            events_manager=events_manager,
            transcriber_factory=transcriber_factory,
            agent_factory=agent_factory,
            synthesizer_factory=synthesizer_factory,
            logger=logger,
        )
        self.logger.info(f"Agent config: {agent_config.json()}")
        self.logger.info(f"Transcriber config: {transcriber_config.json()}")
        self.logger.info(f"Synthesizer config: {synthesizer_config.json()}")

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
        self.logger.info("Attaching websocket...")
        super().attach_ws(ws)
        self.logger.info("Attached websocket")
        # FIXME: discuss and potentially add back those features.

        # self.logger.info("Initializing client...")
        # await self.telephony_client.initialize_client()
        # self.logger.info("Client initialized")
        # twilio_call_ref = self.telephony_client.twilio_client.calls(self.twilio_sid)
        # twilio_call = twilio_call_ref.fetch()
        # self.logger.info(f"Call fetched: {twilio_call.sid}")
        # if self.twilio_config.record:
        #     recordings_create_params = (
        #         self.twilio_config.extra_params.get("recordings_create_params")
        #         if self.twilio_config.extra_params
        #         else None
        #     )
        #     recording = (
        #         twilio_call_ref.recordings.create(**recordings_create_params)
        #         if recordings_create_params
        #         else twilio_call_ref.recordings.create()
        #     )
        #     self.logger.info(f"Recording: {recording.sid}")
        #
        # if twilio_call.answered_by in ("machine_start", "fax"):
        #     self.logger.info(f"Call answered by {twilio_call.answered_by}")
        #     twilio_call.update(status="completed")
        # else:
        await self.wait_for_twilio_start(ws)
        self.logger.info("Starting call...")
        await super().start()
        self.logger.info("Call started")
        self.events_manager.publish_event(
            PhoneCallConnectedEvent(
                conversation_id=self.id,
                to_phone_number=self.to_phone,
                from_phone_number=self.from_phone,
            )
        )
        while self.active:
            message = await ws.receive_text()
            response = await self.handle_ws_message(message)
            if response == PhoneCallWebsocketAction.CLOSE_WEBSOCKET:
                break
        await self.config_manager.delete_config(self.id)
        await self.tear_down()

    async def wait_for_twilio_start(self, ws: WebSocket):
        assert isinstance(self.output_device, TwilioOutputDevice)
        self.logger.info("Waiting for Twilio to start...")
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

    async def handle_ws_message(self, message) -> Optional[PhoneCallWebsocketAction]:
        if message is None:
            return PhoneCallWebsocketAction.CLOSE_WEBSOCKET

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
                await self.receive_audio(b"\xff" * bytes_to_fill)
            self.latest_media_timestamp = int(media["timestamp"])
            await self.receive_audio(chunk)
        elif data["event"] == "stop":
            self.logger.debug(f"Media WS: Received event 'stop': {message}")
            self.logger.debug("Stopping...")
            return PhoneCallWebsocketAction.CLOSE_WEBSOCKET
        return None
