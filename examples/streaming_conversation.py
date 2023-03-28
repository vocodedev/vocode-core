import asyncio
import logging
import signal
from dotenv import load_dotenv

load_dotenv()

from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.helpers import create_microphone_input_and_speaker_output
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
    GoogleTranscriberConfig,
)
from vocode.streaming.models.agent import (
    ChatGPTAgentConfig,
    CutOffResponse,
    FillerAudioConfig,
    RESTfulUserImplementedAgentConfig,
    WebSocketUserImplementedAgentConfig,
    EchoAgentConfig,
    LLMAgentConfig,
    ChatGPTAgentConfig,
)
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import (
    AzureSynthesizerConfig,
    GoogleSynthesizerConfig,
    RimeSynthesizerConfig,
)
import vocode
from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def main():
    microphone_input, speaker_output = create_microphone_input_and_speaker_output(
        streaming=True, use_default_devices=False
    )

    conversation = StreamingConversation(
        output_device=speaker_output,
        transcriber=DeepgramTranscriber(
            DeepgramTranscriberConfig.from_input_device(
                microphone_input, endpointing_config=PunctuationEndpointingConfig()
            )
        ),
        agent=ChatGPTAgent(
            ChatGPTAgentConfig(
                initial_message=BaseMessage(text="What up"),
                prompt_preamble="""You are a helpful gen Z AI assistant. You use slang like um, but, and like a LOT. All of your responses are 10 words or less. Be super chill, use slang like
hella, down,     fire, totally, but like, slay, vibing, queen, go off, bet, sus, simp, cap, big yikes, main character, dank""",
                generate_responses=True,
                cut_off_response=CutOffResponse(),
            )
        ),
        synthesizer=AzureSynthesizer(
            AzureSynthesizerConfig.from_output_device(speaker_output)
        ),
        logger=logger,
    )
    await conversation.start()
    print("Conversation started, press Ctrl+C to end")
    signal.signal(signal.SIGINT, lambda _0, _1: conversation.terminate())
    while conversation.is_active():
        chunk = microphone_input.get_audio()
        if chunk:
            conversation.receive_audio(chunk)
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
