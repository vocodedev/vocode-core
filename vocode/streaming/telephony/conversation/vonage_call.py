from fastapi import WebSocket, WebSocketDisconnect
from enum import Enum
import logging
from typing import Optional
from vocode import getenv
from vocode.streaming.agent.base_agent import BaseAgent
from vocode.streaming.agent.factory import AgentFactory
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.events import PhoneCallConnectedEvent, PhoneCallEndedEvent
from vocode.streaming.output_device.vonage_output_device import VonageOutputDevice

from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.streaming.models.telephony import BaseCallConfig, TwilioConfig, VonageConfig
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
from vocode.streaming.telephony.client.twilio_client import TwilioClient
from vocode.streaming.telephony.client.vonage_client import VonageClient
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)
from vocode.streaming.telephony.constants import DEFAULT_SAMPLING_RATE
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.streaming.telephony.conversation.call import Call
from vocode.streaming.transcriber.base_transcriber import BaseTranscriber
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber
from vocode.streaming.transcriber.factory import TranscriberFactory
from vocode.streaming.utils.events_manager import EventsManager


class PhoneCallAction(Enum):
    CLOSE_WEBSOCKET = 1


class VonageCall(Call[VonageOutputDevice]):
    def __init__(
        self,
        from_phone: str,
        to_phone: str,
        base_url: str,
        config_manager: BaseConfigManager,
        agent_config: AgentConfig,
        transcriber_config: TranscriberConfig,
        synthesizer_config: SynthesizerConfig,
        vonage_config: Optional[VonageConfig] = None,
        vonage_uuid: Optional[str] = None,
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
            VonageOutputDevice(),
            agent_config,
            transcriber_config,
            synthesizer_config,
            conversation_id=conversation_id,
            events_manager=events_manager,
            transcriber_factory=transcriber_factory,
            agent_factory=agent_factory,
            synthesizer_factory=synthesizer_factory,
            logger=logger,
        )
        self.base_url = base_url
        self.config_manager = config_manager
        self.vonage_config = vonage_config or VonageConfig(
            api_key=getenv("VONAGE_API_KEY"),
            api_secret=getenv("VONAGE_API_SECRET"),
            application_id=getenv("VONAGE_APPLICATION_ID"),
            private_key=getenv("VONAGE_PRIVATE_KEY"),
        )
        self.telephony_client = VonageClient(
            base_url=base_url, vonage_config=self.vonage_config
        )
        self.vonage_uuid = vonage_uuid

    # TODO(EPD-186) - make this function async and use aiohttp with the vonage client
    def send_dtmf(self, digits: str):
        self.telephony_client.voice.send_dtmf(self.vonage_uuid, {"digits": digits})

    async def attach_ws_and_start(self, ws: WebSocket):
        # start message
        await ws.receive()
        self.logger.debug("Trying to attach WS to outbound call")
        self.output_device.ws = ws
        self.logger.debug("Attached WS to outbound call")

        await super().start()
        self.events_manager.publish_event(
            PhoneCallConnectedEvent(
                conversation_id=self.id,
                to_phone_number=self.to_phone,
                from_phone_number=self.from_phone,
            )
        )
        while self.active:
            try:
                chunk = await ws.receive_bytes()
                self.receive_audio(chunk)
            except WebSocketDisconnect:
                self.logger.debug("Websocket disconnected")
                break
        self.config_manager.delete_config(self.id)
        self.tear_down()

    def tear_down(self):
        self.events_manager.publish_event(PhoneCallEndedEvent(conversation_id=self.id))
        self.terminate()
