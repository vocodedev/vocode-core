import logging
from fastapi import FastAPI
from vocode.streaming.client_backend.conversation import ConversationRouter
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber

app = FastAPI(docs_url=None)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
