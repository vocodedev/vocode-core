import asyncio
import logging
import signal
from vocode.streaming.hosted_streaming_conversation import HostedStreamingConversation
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.helpers import create_streaming_microphone_input_and_speaker_output
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import AzureSynthesizerConfig
import vocode

vocode.api_key = "<YOUR API KEY>"

logging.basicConfig()
logging.root.setLevel(logging.INFO)


async def main():
    (
        microphone_input,
        speaker_output,
    ) = create_streaming_microphone_input_and_speaker_output(
        use_default_devices=False,
    )

    conversation = HostedStreamingConversation(
        input_device=microphone_input,
        output_device=speaker_output,
        transcriber_config=DeepgramTranscriberConfig.from_input_device(
            microphone_input,
            endpointing_config=PunctuationEndpointingConfig(),
        ),
        agent_config=ChatGPTAgentConfig(
            initial_message=BaseMessage(text="Hello!"),
            prompt_preamble="The AI is having a pleasant conversation about life",
        ),
        synthesizer_config=AzureSynthesizerConfig.from_output_device(speaker_output),
    )
    signal.signal(signal.SIGINT, lambda _0, _1: conversation.deactivate())
    await conversation.start()


if __name__ == "__main__":
    asyncio.run(main())
