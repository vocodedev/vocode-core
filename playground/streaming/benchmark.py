# In this file, write a script that calls multiple transcribers on an audio
# file. Use opentelemetry to get all the stats and then display them in a
# table. Will need a span and metric exporter to save all the data to a
# dictionary or something.

import re
import argparse
import asyncio
import logging
from tqdm import tqdm
from opentelemetry import trace, metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter
from opentelemetry.sdk.metrics.export import (
    InMemoryMetricReader,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.resources import Resource
from vocode.streaming.input_device.file_input_device import FileInputDevice

from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    AssemblyAITranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.transcriber import DeepgramTranscriber, AssemblyAITranscriber

logger = logging.getLogger(__name__)

# Create the parser
parser = argparse.ArgumentParser(
    description="Benchmark Vocode's transcribers, agents, and synthesizers."
)

parser.add_argument(
    "--transcribers",
    type=str,
    nargs="+",
    default=["deepgram", "assemblyai"],
    choices=["deepgram", "assemblyai"],
    help="The list of transcribers to benchmark",
)
parser.add_argument(
    "--agents",
    type=str,
    nargs="+",
    default=["openai_gpt-3.5-turbo"],
    choices=["openai_gpt-3.5-turbo"],
    help="The list of agents to benchmark",
)
parser.add_argument(
    "--synthesizers",
    type=str,
    nargs="+",
    default=["elevenlabs"],
    choices=["elevenlabs"],
    help="The list of synthesizers to benchmark",
)
parser.add_argument(
    "--audio",
    type=str,
    default="test3.wav",
    help="Path to the audio file to transcribe",
)
args = parser.parse_args()


def get_transcriber(transcriber_name, file_input):
    if transcriber_name == "deepgram":
        transcriber = DeepgramTranscriber(
            DeepgramTranscriberConfig.from_input_device(
                file_input,
                endpointing_config=PunctuationEndpointingConfig(),
            )
        )
    elif transcriber_name == "assemblyai":
        transcriber = AssemblyAITranscriber(
            AssemblyAITranscriberConfig.from_input_device(
                file_input,
            )
        )
    return transcriber


trace.set_tracer_provider(TracerProvider(resource=Resource.create({})))
span_exporter = InMemorySpanExporter()
trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(span_exporter))

reader = InMemoryMetricReader()
provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(provider)


async def main():
    sample_rate = 44100
    chunk_size = 2048
    sleep_time = chunk_size / sample_rate
    file_input = FileInputDevice(
        "test3.wav", chunk_size=chunk_size, silent_duration=0.01, skip_initial_load=True
    )

    for transcriber_name in args.transcribers:
        transcriber = get_transcriber(transcriber_name, file_input)
        file_input.load()
        transcriber_task = transcriber.start()

        async def send_audio_task():
            while not file_input.is_done():
                chunk = await file_input.get_audio()
                transcriber.send_audio(chunk)
                await asyncio.sleep(sleep_time)

        send_audio = asyncio.create_task(send_audio_task())

        # `get` from `transcriber.output_queue` until it's empty for 3 seconds
        pbar = tqdm(
            desc=f"{transcriber_name.title()} Transcribing",
            total=file_input.duration,
            unit="chunk",
        )
        while True:
            try:
                transcription = await asyncio.wait_for(
                    transcriber.output_queue.get(), timeout=3
                )
                # update the progress bar status
                pbar.update(round(transcriber.audio_cursor - pbar.n, 2))
            except asyncio.TimeoutError:
                logger.debug(
                    f"[Transcriber: {transcriber_name}] Transcriber queue is empty, stopping transcription..."
                )
                send_audio.cancel()
                break
        pbar.update(pbar.total - pbar.n)
        transcriber.terminate()

    metric_results = (
        reader.get_metrics_data().resource_metrics[0].scope_metrics[0].metrics
    )
    print(metric_results)
    metric_results = {
        metric.name: metric.data.data_points[0] for metric in metric_results
    }
    trace_results = span_exporter.get_finished_spans()
    final_results = {}
    for metric_name, raw_metric in metric_results.items():
        if re.match(r"transcriber.*\.min_latency", metric_name):
            final_results[metric_name] = raw_metric.min
        if re.match(r"transcriber.*\.max_latency", metric_name):
            final_results[metric_name] = raw_metric.max
        if re.match(r"transcriber.*\.avg_latency", metric_name):
            transcriber_str = metric_name.split(".")[1]
            final_results[metric_name] = (
                raw_metric.sum
                / metric_results[f"transcriber.{transcriber_str}.duration"].sum
            )
    print(final_results)


if __name__ == "__main__":
    asyncio.run(main())
