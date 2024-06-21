import asyncio
import signal

from pydantic_settings import BaseSettings, SettingsConfigDict

from vocode.helpers import create_streaming_microphone_input_and_speaker_output
from vocode.logging import configure_pretty_logging
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
# from vocode.streaming.synthesizer.eleven_labs_websocket_synthesizer import ElevenLabsWSSynthesizer
# from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
# from vocode.streaming.models.synthesizer import AzureSynthesizerConfig
from vocode.streaming.models.synthesizer import GoogleSynthesizerConfig, AudioEncoding
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.streaming_conversation import StreamingConversation
# from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.synthesizer.google_synthesizer import GoogleSynthesizer
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber

configure_pretty_logging()


class Settings(BaseSettings):
    """
    Settings for the streaming conversation quickstart.
    These parameters can be configured with environment variables.
    """

    openai_api_key: str = "sk-proj-YeZ7h3bQATXqQfuVCidlT3BlbkFJfyMaB1XDzLrPhtunO0Wq"
    google_service_account_file: str = "/Users/parshva/SoftmaxAI/Projects/vocode-core/sunny-cider-422005-b2-a6428333e2dc.json"
    deepgram_api_key: str = "999a6bd1716edd8ced35b6264a90d929be733974"

    # This means a .env file can be used to overload these settings
    # ex: "OPENAI_API_KEY=my_key" will set openai_api_key over the default above
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
            ),
        ),
        agent=ChatGPTAgent(
            ChatGPTAgentConfig(
                openai_api_key=settings.openai_api_key,
                initial_message=BaseMessage(text="What up"),
                prompt_preamble="""The AI is having a pleasant conversation about life""",
            )
        ),
        synthesizer=GoogleSynthesizer(
            GoogleSynthesizerConfig(
                sampling_rate=24000,
                audio_encoding=AudioEncoding.LINEAR16
            ),
            service_account_file=settings.google_service_account_file
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
