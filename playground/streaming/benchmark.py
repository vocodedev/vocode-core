# In this file, write a script that calls multiple transcribers on an audio
# file. Use opentelemetry to get all the stats and then display them in a
# table. Will need a span and metric exporter to save all the data to a
# dictionary or something.

from collections import defaultdict
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
from vocode.streaming.agent.base_agent import AgentInput
from vocode.streaming.input_device.file_input_device import FileInputDevice
from vocode.streaming.agent import ChatGPTAgent, ChatAnthropicAgent
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.agent import ChatGPTAgentConfig, ChatAnthropicAgentConfig
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    AssemblyAITranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.transcriber import DeepgramTranscriber, AssemblyAITranscriber
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils.worker import InterruptibleEvent

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create the parser
parser = argparse.ArgumentParser(
    description="Benchmark Vocode's transcribers, agents, and synthesizers."
)

transcriber_choices = ["deepgram", "assemblyai"]
agent_choices = ["openai_gpt-3.5-turbo", "anthropic_claude-v1"]
synthesizer_choices = ["elevenlabs"]

parser.add_argument(
    "--transcribers",
    type=str,
    nargs="*",
    default=["deepgram", "assemblyai"],
    choices=transcriber_choices,
    help="The list of transcribers to benchmark",
)
parser.add_argument(
    "--agents",
    type=str,
    nargs="*",
    default=["openai_gpt-3.5-turbo"],
    choices=agent_choices,
    help="The list of agents to benchmark. Each agent should be of the form <company>_<model_name>.",
)
parser.add_argument(
    "--synthesizers",
    type=str,
    nargs="*",
    default=["elevenlabs"],
    choices=synthesizer_choices,
    help="The list of synthesizers to benchmark",
)
parser.add_argument(
    "--transcriber_audio",
    type=str,
    default="test3.wav",
    help="Path to the audio file to transcribe",
)
parser.add_argument(
    "--agent_prompt_preamble",
    type=str,
    default="The AI is having a pleasant conversation about life",
    help="The prompt preamble to use for the agent",
)
parser.add_argument(
    "--agent_first_input",
    type=str,
    default="What is the meaning of life?",
    help="The initial message sent to the agent (this is a transcribed sentence that the agent should respond to).",
)
parser.add_argument(
    "--all",
    action="store_true",
    help="Run all supported transcribers, agents, and synthesizers. Ignores other arguments.",
)
args = parser.parse_args()
if args.all:
    print("--all is set! Running all supported transcribers, agents, and synthesizers.")
    args.transcribers = transcriber_choices
    args.agents = agent_choices
    args.synthesizers = synthesizer_choices


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


async def run_agents():
    for agent_name in tqdm(args.agents, desc="Agents"):
        company, model_name = agent_name.split("_")
        if company == "openai":
            agent = ChatGPTAgent(
                ChatGPTAgentConfig(
                    initial_message=None,
                    prompt_preamble=args.agent_prompt_preamble,
                    allow_agent_to_be_cut_off=False,
                    model_name=model_name,
                )
            )
        elif company == "anthropic":
            agent = ChatAnthropicAgent(
                ChatAnthropicAgentConfig(
                    initial_message=None,
                    allow_agent_to_be_cut_off=False,
                    model_name=model_name,
                )
            )
        agent_task = agent.start()
        message = AgentInput(
            transcription=Transcription(
                message=args.agent_first_input, confidence=1.0, is_final=True
            ),
            conversation_id=0,
        )
        await agent.input_queue.put(InterruptibleEvent(message))

        while True:
            try:
                message = await asyncio.wait_for(agent.output_queue.get(), timeout=5)
                logger.debug(
                    f"[Agent: {agent_name}] Response from API: {message.payload.message.text}"
                )
            except asyncio.TimeoutError:
                logger.debug(f"[Agent: {agent_name}] Agent queue is empty, stopping...")
                break


async def run_transcribers():
    sample_rate = 44100
    chunk_size = 2048
    sleep_time = chunk_size / sample_rate
    file_input = FileInputDevice(
        args.transcriber_audio,
        chunk_size=chunk_size,
        silent_duration=0.01,
        skip_initial_load=True,
    )

    for transcriber_name in tqdm(args.transcribers, desc="Transcribers"):
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


async def main():
    if args.agents:
        await run_agents()
    if args.transcribers:
        await run_transcribers()

    trace_results = span_exporter.get_finished_spans()
    spans = defaultdict(list)
    for span in trace_results:
        duration_ns = span.end_time - span.start_time
        duration_s = duration_ns / 1e9
        spans[span.name].append(duration_s)
    print(spans)

    scope_metrics = reader.get_metrics_data().resource_metrics[0].scope_metrics
    if len(scope_metrics) > 0:
        metric_results = scope_metrics[0].metrics
        print(metric_results)
        metric_results = {
            metric.name: metric.data.data_points[0] for metric in metric_results
        }
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
