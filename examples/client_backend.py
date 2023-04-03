import logging
from fastapi import FastAPI
from dotenv import load_dotenv

from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.synthesizer import AzureSynthesizerConfig

load_dotenv()

from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.client_backend.conversation import ConversationRouter
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.models.websocket import InputAudioConfig
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber
from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer

app = FastAPI(docs_url=None)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

conversation_router = ConversationRouter(
    transcriber_thunk=lambda input_audio_config: DeepgramTranscriber(
        DeepgramTranscriberConfig(
            sampling_rate=input_audio_config.sampling_rate,
            audio_encoding=input_audio_config.audio_encoding,
            chunk_size=input_audio_config.chunk_size,
            endpointing_config=PunctuationEndpointingConfig(),
            downsampling=input_audio_config.downsampling,
        )
    ),
    agent=ChatGPTAgent(
        ChatGPTAgentConfig(
            initial_message=BaseMessage(text="Hello!"),
            prompt_preamble="Have a pleasant conversation about life",
        )
    ),
    synthesizer_thunk=lambda output_audio_config: AzureSynthesizer(
        AzureSynthesizerConfig(
            sampling_rate=output_audio_config.sampling_rate,
            audio_encoding=output_audio_config.audio_encoding,
        )
    ),
    logger=logger,
)

app.include_router(conversation_router.get_router())
