import asyncio
import signal
from os import getenv, path

from dotenv import load_dotenv
from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict

from vocode.helpers import create_streaming_microphone_input_and_speaker_output
from vocode.logging import configure_pretty_logging
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import MurfSynthesizerConfig
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.streaming.synthesizer.murf_synthesizer import MurfSynthesizer
from vocode.streaming.transcriber.assembly_ai_transcriber import AssemblyAITranscriber
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber

configure_pretty_logging()


load_dotenv(path.join(path.dirname(path.dirname(__file__)), ".env"))


class Settings(BaseSettings):
    """
    Settings for the streaming conversation quickstart using Murf synthesizer.
    These parameters can be configured with environment variables.
    """

    openai_api_key: str = getenv("OPENAI_API_KEY", "")
    deepgram_api_key: str = getenv("DEEPGRAM_API_KEY", "")
    murf_api_key: str = getenv("MURF_API_KEY", "")
    murf_voice_id: str = getenv("MURF_VOICE_ID", "en-US-daniel")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


async def main():

    (
        microphone_input,
        speaker_output,
    ) = create_streaming_microphone_input_and_speaker_output(
        use_default_devices=False,
    )

    conversation = StreamingConversation(
        output_device=speaker_output,
        transcriber=DeepgramTranscriber(
            DeepgramTranscriberConfig.from_input_device(
                microphone_input,
                endpointing_config=PunctuationEndpointingConfig(),
                api_key=settings.deepgram_api_key,
                mute_during_speech=True,
            ),
        ),
        agent=ChatGPTAgent(
            ChatGPTAgentConfig(
                openai_api_key=settings.openai_api_key,
                initial_message=BaseMessage(text="What up"),
                prompt_preamble="""You are a helpful and friendly AI assistant having a conversation.""",
            )
        ),
        synthesizer=MurfSynthesizer(
            MurfSynthesizerConfig(
                api_key=settings.murf_api_key,
                voice_id=settings.murf_voice_id,
                format="PCM",
                channel_type="MONO",
                style="Conversational",
                sampling_rate=16000,
                rate=1.0,
                pitch=1.0,
                variation=1.0,
                audio_encoding=AudioEncoding.LINEAR16,
            ),
        ),
    )

    await conversation.start()
    print("Conversation started, press Ctrl+C to end")
    signal.signal(signal.SIGINT, lambda _0, _1: asyncio.create_task(conversation.terminate()))

    while conversation.is_active():
        chunk = await microphone_input.get_audio()
        conversation.receive_audio(chunk)


if __name__ == "__main__":
    asyncio.run(main())
