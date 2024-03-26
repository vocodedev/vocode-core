import os
import signal
from typing import Optional
import logging
import aiohttp
from fastapi import APIRouter, HTTPException, WebSocket
from vocode.streaming.agent.factory import AgentFactory
from vocode.streaming.models.telephony import (
    BaseCallConfig,
    TwilioCallConfig,
    VonageCallConfig,
)
from vocode.streaming.synthesizer.factory import SynthesizerFactory
from vocode.streaming.telephony.config_manager.base_config_manager import (
    BaseConfigManager,
)

from vocode.streaming.telephony.conversation.call import Call
from vocode.streaming.telephony.conversation.twilio_call import TwilioCall
from vocode.streaming.telephony.conversation.vonage_call import VonageCall
from vocode.streaming.transcriber.factory import TranscriberFactory
from vocode.streaming.utils.base_router import BaseRouter
from vocode.streaming.utils.events_manager import EventsManager


async def start_twilio_recording(account_sid, auth_token, call_sid):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls/{call_sid}/Recordings.json"
    auth = aiohttp.BasicAuth(login=account_sid, password=auth_token)
    logger = logging.getLogger(__name__)
    async with aiohttp.ClientSession() as session:
        async with session.post(url, auth=auth) as response:
            if response.status == 201:
                logger.info(f"Started recording for call {call_sid}")
                return await response.json()
            else:
                logger.error(f"Starting recording for call failed {call_sid}!")
                raise HTTPException(status_code=500, detail="Failed to start recording for call")


class CallsRouter(BaseRouter):
    def __init__(
            self,
            base_url: str,
            config_manager: BaseConfigManager,
            transcriber_factory: TranscriberFactory = TranscriberFactory(),
            agent_factory: AgentFactory = AgentFactory(),
            synthesizer_factory: SynthesizerFactory = SynthesizerFactory(),
            events_manager: Optional[EventsManager] = None,
            logger: Optional[logging.Logger] = None,
    ):
        super().__init__()
        self.base_url = base_url
        self.config_manager = config_manager
        self.transcriber_factory = transcriber_factory
        self.agent_factory = agent_factory
        self.synthesizer_factory = synthesizer_factory
        self.events_manager = events_manager
        self.logger = logger or logging.getLogger(__name__)
        self.router = APIRouter()
        self.router.websocket("/connect_call/{id}")(self.connect_call)
        self.active_calls = 0
        self.calls_ran = 0
        max_calls = os.getenv("WORKER_MAX_CALLS", None)
        self.max_calls = int(max_calls) if max_calls is not None else None
        self.logger.info(f"Max calls: {self.max_calls}")

    def _from_call_config(
            self,
            base_url: str,
            call_config: BaseCallConfig,
            config_manager: BaseConfigManager,
            conversation_id: str,
            logger: logging.Logger,
            transcriber_factory: TranscriberFactory = TranscriberFactory(),
            agent_factory: AgentFactory = AgentFactory(),
            synthesizer_factory: SynthesizerFactory = SynthesizerFactory(),
            events_manager: Optional[EventsManager] = None,
    ):
        if isinstance(call_config, TwilioCallConfig):
            return TwilioCall(
                to_phone=call_config.to_phone,
                from_phone=call_config.from_phone,
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
        elif isinstance(call_config, VonageCallConfig):
            return VonageCall(
                to_phone=call_config.to_phone,
                from_phone=call_config.from_phone,
                base_url=base_url,
                logger=logger,
                config_manager=config_manager,
                agent_config=call_config.agent_config,
                transcriber_config=call_config.transcriber_config,
                synthesizer_config=call_config.synthesizer_config,
                vonage_config=call_config.vonage_config,
                vonage_uuid=call_config.vonage_uuid,
                conversation_id=conversation_id,
                transcriber_factory=transcriber_factory,
                agent_factory=agent_factory,
                synthesizer_factory=synthesizer_factory,
                events_manager=events_manager,
                output_to_speaker=call_config.output_to_speaker,
            )
        else:
            raise ValueError(f"Unknown call config type {call_config.type}")

    async def connect_call(self, websocket: WebSocket, id: str):
        try:
            self.logger.info("Opening Phone WS for chat {}".format(id))
            await websocket.accept()
            self.logger.info("Phone WS connection opened for chat {}".format(id))
            call_config = await self.config_manager.get_config(id)
            self.logger.info(f"Got call config for {id}")
            if not call_config:
                raise HTTPException(status_code=400, detail="No active phone call")
            self.active_calls += 1
            self.calls_ran += 1
            call = self._from_call_config(
                base_url=self.base_url,
                call_config=call_config,
                config_manager=self.config_manager,
                conversation_id=id,
                transcriber_factory=self.transcriber_factory,
                agent_factory=self.agent_factory,
                synthesizer_factory=self.synthesizer_factory,
                events_manager=self.events_manager,
                logger=self.logger,
            )
            self.logger.info(f"Call: {call}")
            self.logger.info("starting recording")
            await start_twilio_recording(call.twilio_config.account_sid, call.twilio_config.auth_token, call.twilio_sid)

            await call.attach_ws_and_start(websocket)
            self.logger.debug("Phone WS connection closed for chat {}".format(id))
        finally:
            self.active_calls -= 1
            if self.max_calls is not None and self.calls_ran >= self.max_calls:
                self.logger.info("Max calls reached, shutting down")
                # Graceful shutdown must be implemented in FASTAPI to avoid killing active calls.
                os.kill(os.getpid(), signal.SIGTERM)

    def get_router(self) -> APIRouter:
        return self.router
