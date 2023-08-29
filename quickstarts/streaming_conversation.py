import asyncio
import logging
import signal
from dotenv import load_dotenv
from vocode.streaming.transcriber.base_transcriber import Transcription


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


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def main():
    (
        microphone_input,
        speaker_output,
    ) = create_streaming_microphone_input_and_speaker_output(
        # input_device_name="krisp microphone",
        # output_device_name="krisp speaker",
        # input_device_name="Ajay's AirPod Pros",
        # output_device_name="Ajay's AirPod Pros",
        use_default_devices=False,
        logger=logger,
        use_blocking_speaker_output=True,  # this moves the playback to a separate thread, set to False to use the main thread
    )

    conversation = StreamingConversation(
        output_device=speaker_output,
        transcriber=DeepgramTranscriber(
            DeepgramTranscriberConfig.from_input_device(
                microphone_input,
                endpointing_config=PunctuationEndpointingConfig(),
            )
        ),
        agent=ChatGPTAgent(
            ChatGPTAgentConfig(
                # initial_message=BaseMessage(text="What up"),
                prompt_preamble="""The AI is having a pleasant conversation about life""",
                send_text_chunks_to_synthesizer=True,
                # max_tokens=10,
            )
        ),
        # synthesizer=AzureSynthesizer(
        #     AzureSynthesizerConfig.from_output_device(speaker_output)
        # ),
        synthesizer=ElevenLabsSynthesizer(
            ElevenLabsSynthesizerConfig.from_output_device(
                speaker_output, accept_input_chunks=True
            )
        ),
        logger=logger,
    )
    await conversation.start()
    print("Conversation started, press Ctrl+C to end")
    signal.signal(
        signal.SIGINT, lambda _0, _1: asyncio.create_task(conversation.terminate())
    )
    conversation.transcriptions_worker.input_queue.put_nowait(
        Transcription(
            message="hi",
            confidence=1,
            is_final=True,
        )
    )
    while conversation.is_active():
        chunk = await microphone_input.get_audio()
        conversation.receive_audio(chunk)


if __name__ == "__main__":
    asyncio.run(main())
