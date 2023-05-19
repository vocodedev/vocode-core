import asyncio
import logging
import signal
from dotenv import load_dotenv

from vocode.streaming.synthesizer.caching_synthesizer import CachingSynthesizer


load_dotenv()

from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.helpers import create_streaming_microphone_input_and_speaker_output
from vocode.streaming.transcriber import *
from vocode.streaming.agent import *
from vocode.streaming.synthesizer import *
from vocode.streaming.models.transcriber import *
from vocode.streaming.models.agent import *
from vocode.streaming.models.synthesizer import *
from vocode.streaming.models.message import BaseMessage


logging.basicConfig(format='%(relativeCreated)d - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

async def main():
    (
        microphone_input,
        speaker_output,
    ) = create_streaming_microphone_input_and_speaker_output(use_default_devices=True)

    conversation = StreamingConversation(
        output_device=speaker_output,
        transcriber=AzureTranscriber(
            AzureTranscriberConfig.from_input_device(
                microphone_input
            )
        ),
        agent=ChatGPTAgent(
            ChatGPTAgentConfig(
                initial_message=BaseMessage(text="What up"),
                prompt_preamble="""The AI is having a pleasant conversation about life""",
                end_conversation_on_goodbye=True,
                track_bot_sentiment=True,
                send_filler_audio=True,
            )
        ),
        synthesizer=CachingSynthesizer(AzureSynthesizer(
            AzureSynthesizerConfig.from_output_device(speaker_output)
        )),
        logger=logger,
    )
    await conversation.start()
    print("Conversation started, press Ctrl+C to end")
    signal.signal(signal.SIGINT, lambda _0, _1: conversation.terminate())
    while conversation.is_active():
        chunk = await microphone_input.get_audio()
        conversation.receive_audio(chunk)


if __name__ == "__main__":
    asyncio.run(main())
