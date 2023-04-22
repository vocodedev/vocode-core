import logging
import os
import typing
from fastapi import FastAPI
from dotenv import load_dotenv
from vocode.streaming.models.events import Event, EventType, TranscriptCompleteEvent

from vocode.streaming.utils import events_manager

load_dotenv()

from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)
from vocode.streaming.telephony.server.base import TelephonyServer

app = FastAPI(docs_url=None)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class EventsManager(events_manager.EventsManager):
    def __init__(self):
        super().__init__(subscriptions=[EventType.TRANSCRIPT_COMPLETE])

    def handle_event(self, event: Event):
        if event.type == EventType.TRANSCRIPT_COMPLETE:
            transcript_complete_event = typing.cast(TranscriptCompleteEvent, event)
            with open("examples/babyagi/call_transcripts/{}.txt".format(event.conversation_id), "w") as f:
                f.write(transcript_complete_event.transcript)

config_manager = RedisConfigManager()

BASE_URL = os.getenv("TELEPHONY_SERVER_BASE_URL")

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[],
    events_manager=EventsManager(),
    logger=logger,
)

app.include_router(telephony_server.get_router())
