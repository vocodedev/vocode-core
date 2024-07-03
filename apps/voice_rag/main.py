import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI

from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.client_backend.conversation import ConversationRouter
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import AzureSynthesizerConfig
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig, TimeEndpointingConfig
from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber
from vocode.streaming.vector_db.factory import VectorDBFactory
from vocode.streaming.vector_db.pinecone import PineconeConfig

load_dotenv()

app = FastAPI(docs_url=None)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Ensure that the environment variable 'PINECONE_INDEX_NAME' is not None
pinecone_index_name = os.getenv("PINECONE_INDEX_NAME")
if pinecone_index_name is None:
    raise ValueError("Environment variable 'PINECONE_INDEX_NAME' is not set.")

vector_db_config = PineconeConfig(index=pinecone_index_name)

INITIAL_MESSAGE = "Hello!"
PROMPT_PREAMBLE = """
I want you to act as an IT Architect. 
I will provide some details about the functionality of an application or other 
digital product, and it will be your job to come up with ways to integrate it 
into the IT landscape. This could involve analyzing business requirements, 
performing a gap analysis, and mapping the functionality of the new system to 
the existing IT landscape. The next steps are to create a solution design. 

You are an expert in these technologies: 
- Langchain
- Supabase
- Next.js
- Fastapi
- Vocode.
"""

TIME_ENDPOINTING_CONFIG = TimeEndpointingConfig()
TIME_ENDPOINTING_CONFIG.time_cutoff_seconds = 2

AZURE_SYNTHESIZER_THUNK = lambda output_audio_config: AzureSynthesizer(
    AzureSynthesizerConfig.from_output_audio_config(
        output_audio_config,
    ),
    logger=logger,
)

DEEPGRAM_TRANSCRIBER_THUNK = lambda input_audio_config: DeepgramTranscriber(
    DeepgramTranscriberConfig.from_input_audio_config(
        input_audio_config=input_audio_config,
        endpointing_config=TIME_ENDPOINTING_CONFIG,
        min_interrupt_confidence=0.9,
    ),
    logger=logger,
)

conversation_router = ConversationRouter(
    agent_thunk=lambda: ChatGPTAgent(
        ChatGPTAgentConfig(
            initial_message=BaseMessage(text=INITIAL_MESSAGE),
            prompt_preamble=PROMPT_PREAMBLE,
            vector_db_config=vector_db_config,
        ),
        logger=logger,
    ),
    synthesizer_thunk=AZURE_SYNTHESIZER_THUNK,
    transcriber_thunk=DEEPGRAM_TRANSCRIBER_THUNK,
    logger=logger,
)

app.include_router(conversation_router.get_router())
