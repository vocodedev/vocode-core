import asyncio
import logging
import signal

from vocode.conversation import Conversation
from vocode.helpers import create_microphone_input_and_speaker_output
from vocode.models.transcriber import DeepgramTranscriberConfig
from vocode.models.agent import ChatGPTAgentConfig, RESTfulUserImplementedAgentConfig
from vocode.models.synthesizer import AzureSynthesizerConfig
from vocode.user_implemented_agent.restful_agent import RESTfulAgent

logging.basicConfig()
logging.root.setLevel(logging.INFO)

class EchoAgent(RESTfulAgent):

    async def respond(self, input: str) -> str:
        return input

if __name__ == "__main__":
    import threading

    microphone_input, speaker_output = create_microphone_input_and_speaker_output(use_first_available_device=False)
    user_agent_thread = threading.Thread(target=EchoAgent().run)
    user_agent_thread.start()

    conversation = Conversation(
        input_device=microphone_input,
        output_device=speaker_output,
        transcriber_config=DeepgramTranscriberConfig.from_input_device(microphone_input),
        agent_config=RESTfulUserImplementedAgentConfig(
            initial_message="Hello!",
            generate_responses=False,
            respond=RESTfulUserImplementedAgentConfig.EndpointConfig(
                url="http://localhost:3001/respond",
                method="POST"
            )
        ),
        synthesizer_config=AzureSynthesizerConfig.from_output_device(speaker_output)
    )
    signal.signal(signal.SIGINT, lambda _0, _1: conversation.deactivate())
    asyncio.run(conversation.start())
    user_agent_thread.join()

