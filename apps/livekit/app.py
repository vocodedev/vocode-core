import asyncio
import os

from livekit.agents import JobContext, JobRequest, WorkerOptions, cli
from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict

from svara.logging import configure_pretty_logging
from svara.streaming.action.end_conversation import EndConversationVocodeActionConfig
from svara.streaming.agent.chat_gpt_agent import ChatGPTAgent
from svara.streaming.livekit.livekit_conversation import LiveKitConversation
from svara.streaming.models.actions import (
    PhraseBasedActionTrigger,
    PhraseBasedActionTriggerConfig,
    PhraseTrigger,
)
from svara.streaming.models.agent import ChatGPTAgentConfig
from svara.streaming.models.message import BaseMessage
from svara.streaming.models.synthesizer import AzureSynthesizerConfig
from svara.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from svara.streaming.output_device.livekit_output_device import LiveKitOutputDevice
from svara.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from svara.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber


class Settings(BaseSettings):

    livekit_api_key: str = "ENTER_YOUR_LIVE_KIT_API_KEY"
    livekit_api_secret: str = "ENTER_YOUR_LIVE_KIT_API_SECRET"
    livekit_ws_url: str = "ENTER_YOUR_LIVE_KIT_WS_URL"

    # This means a .env file can be used to overload these settings
    # ex: "OPENAI_API_KEY=my_key" will set openai_api_key over the default above
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


async def wait_for_termination(conversation: LiveKitConversation, ctx: JobContext):
    await conversation.wait_for_termination()
    await conversation.terminate()
    await ctx.room.disconnect()


async def entrypoint(ctx: JobContext):
    configure_pretty_logging()
    output_device = LiveKitOutputDevice()
    conversation = LiveKitConversation(
        output_device=output_device,
        transcriber=DeepgramTranscriber(
            DeepgramTranscriberConfig.from_livekit_input_device(
                endpointing_config=PunctuationEndpointingConfig(),
                api_key=os.getenv("DEEPGRAM_API_KEY"),
            ),
        ),
        agent=ChatGPTAgent(
            ChatGPTAgentConfig(
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                initial_message=BaseMessage(text="What up"),
                prompt_preamble="""The AI is having a pleasant conversation about life""",
                actions=[
                    EndConversationVocodeActionConfig(
                        action_trigger=PhraseBasedActionTrigger(
                            config=PhraseBasedActionTriggerConfig(
                                phrase_triggers=[
                                    PhraseTrigger(
                                        phrase="goodbye",
                                        conditions=["phrase_condition_type_contains"],
                                    )
                                ]
                            )
                        )
                    )
                ],
            )
        ),
        synthesizer=AzureSynthesizer(
            synthesizer_config=AzureSynthesizerConfig.from_output_device(
                output_device=output_device,
                voice_name="en-US-AriaNeural",
            )
        ),
    )
    await conversation.start_room(ctx.room)
    asyncio.create_task(wait_for_termination(conversation, ctx))


async def request_fnc(req: JobRequest) -> None:
    logger.info("received request %s", req)
    await req.accept(entrypoint)


if __name__ == "__main__":
    settings = Settings()
    cli.run_app(
        WorkerOptions(
            request_fnc,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            ws_url=settings.livekit_ws_url,
        )
    )
