from dotenv import load_dotenv

load_dotenv()

import typing
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)
from vocode.streaming.models.events import Event, EventType, TranscriptCompleteEvent
from vocode.streaming.utils import events_manager
from vocode.streaming.telephony.server.base import TelephonyServer
import logging


app = FastAPI(docs_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_manager = RedisConfigManager()

BASE_URL = "your ngrok url"


class EventsManager(events_manager.EventsManager):
    def __init__(self):
        super().__init__(subscriptions=[EventType.TRANSCRIPT_COMPLETE])

    def handle_event(self, event: Event):
        if event.type == EventType.TRANSCRIPT_COMPLETE:
            transcript_complete_event = typing.cast(TranscriptCompleteEvent, event)
            with open(
                "call_transcripts/{}.txt".format(event.conversation_id),
                "w",
            ) as f:
                f.write(transcript_complete_event.transcript)


telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    logger=logger,
    events_manager=EventsManager(),
)

app.include_router(telephony_server.get_router())
