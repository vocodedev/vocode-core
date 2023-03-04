import asyncio
import logging
import signal

from vocode.conversation import Conversation
from vocode.helpers import create_microphone_input_and_speaker_output
from vocode.models.transcriber import DeepgramTranscriberConfig
from vocode.models.agent import ChatGPTAgentConfig, RESTfulUserImplementedAgentConfig, WebSocketUserImplementedAgentConfig, EchoAgentConfig, ChatGPTAlphaAgentConfig, ChatGPTAgentConfig
from vocode.models.synthesizer import AzureSynthesizerConfig
from vocode.user_implemented_agent.restful_agent import RESTfulAgent

logging.basicConfig()
logging.root.setLevel(logging.INFO)


if __name__ == "__main__":
    microphone_input, speaker_output = create_microphone_input_and_speaker_output(use_default_devices=False)

    conversation = Conversation(
        input_device=microphone_input,
        output_device=speaker_output,
        transcriber_config=DeepgramTranscriberConfig.from_input_device(microphone_input),
        agent_config=EchoAgentConfig(initial_message="Hello!"),
        synthesizer_config=AzureSynthesizerConfig.from_output_device(speaker_output)
    )
    signal.signal(signal.SIGINT, lambda _0, _1: conversation.deactivate())
    asyncio.run(conversation.start())

