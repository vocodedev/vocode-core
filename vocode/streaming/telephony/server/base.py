import abc
import logging
from functools import partial
from typing import List, Optional, Callable

from fastapi import APIRouter, Form, Request, Response
from pydantic import BaseModel, Field
from vocode.streaming.agent.factory import AgentFactory
from vocode.streaming.models.agent import AgentConfig
from vocode.streaming.models.events import RecordingEvent
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.models.telephony import (
    TwilioCallConfig,
    TwilioConfig,
    VonageCallConfig,
    VonageConfig,
)
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.synthesizer.factory import SynthesizerFactory
from vocode.streaming.telephony.client.twilio_client import TwilioClient
from vocode.streaming.telephony.client.vonage_client import VonageClient
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)
from vocode.streaming.telephony.server.router.calls import CallsRouter
from vocode.streaming.telephony.templater import Templater
from vocode.streaming.transcriber.factory import TranscriberFactory
from vocode.streaming.utils import create_conversation_id
from vocode.streaming.utils.events_manager import EventsManager


class AbstractInboundCallConfig(BaseModel, abc.ABC):
    url: str
    agent_config: AgentConfig
    transcriber_config: Optional[TranscriberConfig] = None
    synthesizer_config: Optional[SynthesizerConfig] = None


class TwilioInboundCallConfig(AbstractInboundCallConfig):
    twilio_config: TwilioConfig


class VonageInboundCallConfig(AbstractInboundCallConfig):
    vonage_config: VonageConfig


class VonageAnswerRequest(BaseModel):
    to: str
    from_: str = Field(..., alias="from")
    uuid: str


class TelephonyServer:
    def __init__(
            self,
            base_url: str,
            config_manager: BaseConfigManager,
            inbound_call_configs: List[AbstractInboundCallConfig] = [],
            transcriber_factory: TranscriberFactory = TranscriberFactory(),
            agent_factory: AgentFactory = AgentFactory(),
            synthesizer_factory: SynthesizerFactory = SynthesizerFactory(),
            events_manager: Optional[EventsManager] = None,
            logger: Optional[logging.Logger] = None,
            get_data: Optional[Callable] = None,
            setup_agent_config: Optional[Callable] = None,
    ):
        self.base_url = base_url
        self.logger = logger or logging.getLogger(__name__)
        self.router = APIRouter()
        self.config_manager = config_manager
        self.templater = Templater()
        self.events_manager = events_manager
        self.get_data = get_data
        self.setup_agent_config = setup_agent_config
        self.calls_router = CallsRouter(
            base_url=base_url,
            config_manager=self.config_manager,
            transcriber_factory=transcriber_factory,
            agent_factory=agent_factory,
            synthesizer_factory=synthesizer_factory,
            events_manager=self.events_manager,
            logger=self.logger,
        )
        self.router.include_router(
            self.calls_router.get_router()
        )
        for config in inbound_call_configs:
            self.router.add_api_route(
                config.url,
                self.create_inbound_route(inbound_call_config=config),
                methods=["POST"],
            )
        # vonage requires an events endpoint
        self.router.add_api_route("/events", self.events, methods=["GET", "POST"])
        self.logger.info(f"Set up events endpoint at https://{self.base_url}/events")

    def events(self, request: Request):
        return Response()

    def get_reroute_twiml(self, number_to_dial: str):
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say>Redirecting your call.</Say>
            <Dial>{number_to_dial}</Dial>
        </Response>"""
        return Response(twiml, media_type="application/xml")

    def create_inbound_route(
            self,
            inbound_call_config: AbstractInboundCallConfig,
    ):
        async def twilio_route(
                twilio_config: TwilioConfig,
                twilio_sid: str = Form(alias="CallSid"),
                twilio_from: str = Form(alias="From"),
                twilio_to: str = Form(alias="To"),
        ) -> Response:
            # TODO: rewrite it. Not generic.
            transcriber_config = inbound_call_config.transcriber_config or TwilioCallConfig.default_transcriber_config()
            agent_config = inbound_call_config.agent_config
            synthesizer_config = inbound_call_config.synthesizer_config or TwilioCallConfig.default_synthesizer_config()
            dialog_state, prompt_template_filename, _ = await self.get_data(twilio_from)
            agent_config.prompt_template_filename = prompt_template_filename
            synthesizer_config.prompt_template_filename = prompt_template_filename
            if dialog_state is None:
                return self.get_reroute_twiml(number_to_dial="+420792212893")  # Real person number.
            agent_config = await self.setup_agent_config(phone_number=twilio_from,
                                                         synthesizer_config=synthesizer_config,
                                                         agent_config=agent_config,
                                                         dialog_state=dialog_state,
                                                         inbound_call=True)
            call_config = TwilioCallConfig(
                transcriber_config=transcriber_config,
                agent_config=agent_config,
                synthesizer_config=synthesizer_config,
                twilio_config=twilio_config,
                twilio_sid=twilio_sid,
                from_phone=twilio_from,
                to_phone=twilio_to,
            )
            #
            conversation_id = create_conversation_id()
            await self.config_manager.save_config(conversation_id, call_config)
            return self.templater.get_connection_twiml(
                base_url=self.base_url, call_id=conversation_id
            )

        async def vonage_route(
                vonage_config: VonageConfig, vonage_answer_request: VonageAnswerRequest
        ):
            call_config = VonageCallConfig(
                transcriber_config=inbound_call_config.transcriber_config
                                   or VonageCallConfig.default_transcriber_config(),
                agent_config=inbound_call_config.agent_config,
                synthesizer_config=inbound_call_config.synthesizer_config
                                   or VonageCallConfig.default_synthesizer_config(),
                vonage_config=vonage_config,
                vonage_uuid=vonage_answer_request.uuid,
                to_phone=vonage_answer_request.from_,
                from_phone=vonage_answer_request.to,
            )
            conversation_id = create_conversation_id()
            await self.config_manager.save_config(conversation_id, call_config)
            return VonageClient.create_call_ncco(
                base_url=self.base_url, conversation_id=conversation_id, record=vonage_config.record
            )

        if isinstance(inbound_call_config, TwilioInboundCallConfig):
            self.logger.info(
                f"Set up inbound call TwiML at https://{self.base_url}{inbound_call_config.url}"
            )
            return partial(twilio_route, inbound_call_config.twilio_config)
        elif isinstance(inbound_call_config, VonageInboundCallConfig):
            self.logger.info(
                f"Set up inbound call NCCO at https://{self.base_url}{inbound_call_config.url}"
            )
            return partial(vonage_route, inbound_call_config.vonage_config)
        else:
            raise ValueError(
                f"Unknown inbound call config type {type(inbound_call_config)}"
            )

    async def end_outbound_call(self, conversation_id: str):
        # TODO validation via twilio_client
        call_config = await self.config_manager.get_config(conversation_id)
        if not call_config:
            raise ValueError(f"Could not find call config for {conversation_id}")
        if isinstance(call_config, TwilioCallConfig):
            telephony_client = TwilioClient(
                base_url=self.base_url, twilio_config=call_config.twilio_config
            )
            await telephony_client.initialize_client()
            await telephony_client.end_call(call_config.twilio_sid)
        elif isinstance(call_config, VonageCallConfig):
            telephony_client = VonageClient(
                base_url=self.base_url, vonage_config=call_config.vonage_config
            )
            await telephony_client.end_call(call_config.vonage_uuid)
        return {"id": conversation_id}

    def get_router(self) -> APIRouter:
        return self.router
