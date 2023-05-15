import asyncio
from collections import defaultdict
import logging
import signal
from dotenv import load_dotenv
from vocode.streaming.synthesizer.coqui_tts_synthesizer import CoquiTTSSynthesizer

from vocode.streaming.synthesizer.eleven_labs_synthesizer import ElevenLabsSynthesizer
from vocode.streaming.synthesizer.gtts_synthesizer import GTTSSynthesizer
from vocode.streaming.synthesizer.play_ht_synthesizer import PlayHtSynthesizer
from vocode.streaming.synthesizer.rime_synthesizer import RimeSynthesizer
from vocode.streaming.transcriber.google_transcriber import GoogleTranscriber
from vocode.streaming.transcriber.whisper_cpp_transcriber import WhisperCPPTranscriber

load_dotenv()

from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.streaming_conversation import StreamingConversation
from vocode.helpers import create_microphone_input_and_speaker_output
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
    GoogleTranscriberConfig,
    WhisperCPPTranscriberConfig,
)
from vocode.streaming.models.agent import (
    FILLER_AUDIO_DEFAULT_SILENCE_THRESHOLD_SECONDS,
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
    CoquiTTSSynthesizerConfig,
    ElevenLabsSynthesizerConfig,
    GTTSSynthesizerConfig,
    GoogleSynthesizerConfig,
    PlayHtSynthesizerConfig,
    RimeSynthesizerConfig,
)
import vocode
from vocode.streaming.synthesizer.azure_synthesizer import AzureSynthesizer
from vocode.streaming.transcriber.deepgram_transcriber import DeepgramTranscriber

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter
from opentelemetry.sdk.resources import Resource


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PrintDurationSpanExporter(SpanExporter):
    def __init__(self):
        super().__init__()
        self.spans = defaultdict(list)

    def export(self, spans):
        for span in spans:
            duration_ns = span.end_time - span.start_time
            duration_s = duration_ns / 1e9
            self.spans[span.name].append(duration_s)

    def shutdown(self):
        for name, durations in self.spans.items():
            print(f"{name}: {sum(durations) / len(durations)}")


trace.set_tracer_provider(TracerProvider(resource=Resource.create({})))
trace.get_tracer_provider().add_span_processor(
    SimpleSpanProcessor(PrintDurationSpanExporter())
)


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
                prompt_preamble="""The AI is having a pleasant conversation about life""",
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
