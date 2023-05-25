from opentelemetry import trace, metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, InMemoryMetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.resources import Resource
from collections import defaultdict


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
span_exporter = InMemorySpanExporter()
trace.get_tracer_provider().add_span_processor(
    SimpleSpanProcessor(span_exporter)
)
reader = InMemoryMetricReader()
provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(provider)

import asyncio
import logging
import signal
from dotenv import load_dotenv


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
from vocode.streaming.input_device.file_input_device import FileInputDevice


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def main():
    (
        microphone_input,
        speaker_output,
    ) = create_streaming_microphone_input_and_speaker_output(use_default_devices=False)
    file_input = FileInputDevice("test3.wav")

    conversation = StreamingConversation(
        output_device=speaker_output,
        transcriber=DeepgramTranscriber(
            DeepgramTranscriberConfig.from_input_device(
                file_input,
                endpointing_config=PunctuationEndpointingConfig(),
            )
        ),
        agent=ChatGPTAgent(
            ChatGPTAgentConfig(
                initial_message=BaseMessage(text="What up"),
                prompt_preamble="""The AI is having a pleasant conversation about life""",
                allow_agent_to_be_cut_off=False,
            )
        ),
        synthesizer=AzureSynthesizer(
            AzureSynthesizerConfig.from_output_device(speaker_output)
        ),
        logger=logger,
    )
    await conversation.start()
    print("Conversation started, press Ctrl+C to end")
    def thing():
        conversation.terminate()
        metric_results = reader.get_metrics_data()
        trace_results = span_exporter.get_finished_spans()
        print(metric_results)
        print("**************")
        print(trace_results)
    signal.signal(signal.SIGINT, lambda _0, _1: thing())
    while conversation.is_active():
        chunk = await microphone_input.get_audio()
        conversation.receive_audio(chunk)


if __name__ == "__main__":
    asyncio.run(main())
