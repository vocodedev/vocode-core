import asyncio
import logging
import signal
from dotenv import load_dotenv
import os

load_dotenv()

import vocode

vocode.api_key = os.getenv("VOCODE_API_KEY")

from vocode.conversation import Conversation
from vocode.helpers import create_microphone_input_and_speaker_output
from vocode.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
    GoogleTranscriberConfig,
)
from vocode.models.agent import (
    ChatGPTAgentConfig,
    FillerAudioConfig,
    RESTfulUserImplementedAgentConfig,
    WebSocketUserImplementedAgentConfig,
    EchoAgentConfig,
    ChatGPTAlphaAgentConfig,
    LLMAgentConfig,
    ChatGPTAgentConfig,
)
from vocode.models.message import BaseMessage
from vocode.models.synthesizer import AzureSynthesizerConfig
from vocode.user_implemented_agent.restful_agent import RESTfulAgent

logging.basicConfig()
logging.root.setLevel(logging.INFO)


if __name__ == "__main__":
    microphone_input, speaker_output = create_microphone_input_and_speaker_output(
        use_default_devices=False
    )

    conversation = Conversation(
        input_device=microphone_input,
        output_device=speaker_output,
        transcriber_config=DeepgramTranscriberConfig.from_input_device(
            microphone_input
        ),
        agent_config=ChatGPTAgentConfig(
            initial_message=BaseMessage(text="Hello!"),
            prompt_preamble="The AI is having a pleasant conversation about life.",
            generate_responses=False,
            end_conversation_on_goodbye=True,
            send_filler_audio=FillerAudioConfig(use_typing_noise=True),
        ),
        synthesizer_config=AzureSynthesizerConfig.from_output_device(speaker_output),
    )
    signal.signal(signal.SIGINT, lambda _0, _1: conversation.deactivate())
    asyncio.run(conversation.start())
