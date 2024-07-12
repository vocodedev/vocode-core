import logging
import os
import typing

from call_transcript_utils import add_transcript
from dotenv import load_dotenv
from fastapi import FastAPI

from vocode.streaming.models.events import Event
from vocode.streaming.models.transcript import TranscriptCompleteEvent
from vocode.streaming.telephony.config_manager.redis_config_manager import RedisConfigManager
from vocode.streaming.telephony.server.base import TelephonyServer
from vocode.streaming.utils import events_manager

load_dotenv()

app = FastAPI(docs_url=None)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class EventsManager(events_manager.EventsManager):
    def __init__(self):
        super().__init__(subscriptions=["transcript_complete"])

    async def handle_event(self, event: Event):
        if isinstance(event, TranscriptCompleteEvent):
            add_transcript(
                event.conversation_id,
                event.transcript.to_string(),
            )


config_manager = RedisConfigManager()

BASE_URL = os.environ["TELEPHONY_SERVER_BASE_URL"]

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[],
    events_manager=EventsManager(),
    logger=logger,
)

app.include_router(telephony_server.get_router())
