from dotenv import load_dotenv
from fastapi import FastAPI

from svara.logging import configure_pretty_logging
from svara.streaming.agent.chat_gpt_agent import ChatGPTAgent
from svara.streaming.client_backend.conversation import ConversationRouter
from svara.streaming.models.agent import ChatGPTAgentConfig
from svara.streaming.models.message import BaseMessage
from svara.streaming.models.synthesizer import AzureSynthesizerConfig
from svara.streaming.synthesizer.azure_synthesizer import AzureSynthesizer

load_dotenv()

app = FastAPI(docs_url=None)

configure_pretty_logging()

conversation_router = ConversationRouter(
    agent_thunk=lambda: ChatGPTAgent(
        ChatGPTAgentConfig(
            initial_message=BaseMessage(text="Hello!"),
            prompt_preamble="Have a pleasant conversation about life",
        )
    ),
    synthesizer_thunk=lambda output_audio_config: AzureSynthesizer(
        AzureSynthesizerConfig.from_output_audio_config(
            output_audio_config, voice_name="en-US-SteffanNeural"
        )
    ),
)

app.include_router(conversation_router.get_router())
