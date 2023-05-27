import os
import re
import json
import argparse
import asyncio
import logging
from tqdm import tqdm
from opentelemetry import trace, metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
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
from vocode.streaming.models.synthesizer import (
    AzureSynthesizerConfig,
    BarkSynthesizerConfig,
    CoquiSynthesizerConfig,
    CoquiTTSSynthesizerConfig,
    ElevenLabsSynthesizerConfig,
    GTTSSynthesizerConfig,
    GoogleSynthesizerConfig,
    PlayHtSynthesizerConfig,
    RimeSynthesizerConfig,
    StreamElementsSynthesizerConfig,
)
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    AssemblyAITranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.models.transcript import Transcript
from vocode.streaming.output_device.file_output_device import FileOutputDevice
from vocode.streaming.synthesizer import (
    AzureSynthesizer,
    BarkSynthesizer,
    CoquiSynthesizer,
    CoquiTTSSynthesizer,
    ElevenLabsSynthesizer,
    GTTSSynthesizer,
    GoogleSynthesizer,
    PlayHtSynthesizer,
    RimeSynthesizer,
    StreamElementsSynthesizer,
)
from vocode.streaming.transcriber import DeepgramTranscriber, AssemblyAITranscriber
from vocode.streaming.transcriber.base_transcriber import Transcription
from vocode.streaming.utils import get_chunk_size_per_second
from vocode.streaming.utils.worker import InterruptibleEvent

logger = logging.getLogger(__name__)
logging.basicConfig()

logger.setLevel(logging.DEBUG)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)


# Create the parser
parser = argparse.ArgumentParser(
    description="Benchmark Vocode's transcribers, agents, and synthesizers."
)

synthesizer_classes = {
    "elevenlabs": (ElevenLabsSynthesizer, ElevenLabsSynthesizerConfig),
    "azure": (AzureSynthesizer, AzureSynthesizerConfig),
    "bark": (BarkSynthesizer, BarkSynthesizerConfig),
    "coqui": (CoquiSynthesizer, CoquiSynthesizerConfig),
    "coquitts": (CoquiTTSSynthesizer, CoquiTTSSynthesizerConfig),
    "google": (GoogleSynthesizer, GoogleSynthesizerConfig),
    "gtts": (GTTSSynthesizer, GTTSSynthesizerConfig),
    "playht": (PlayHtSynthesizer, PlayHtSynthesizerConfig),
    "rime": (RimeSynthesizer, RimeSynthesizerConfig),
    "streamelements": (StreamElementsSynthesizer, StreamElementsSynthesizerConfig),
}

synthesizer_classes = {
    k: v
    for k, v in synthesizer_classes.items()
    if k not in ["coqui", "coquitts", "bark"]
}

# These synthesizers stream output so they need to be traced within this file.
STREAMING_SYNTHESIZERS = ["azure"]


transcriber_choices = ["deepgram", "assemblyai"]
agent_choices = [
    "openai_gpt-3.5-turbo",
    "openai_gpt-4",
    "anthropic_claude-v1",
    "anthropic_claude-instant-v1",
]
synthesizer_choices = list(synthesizer_classes)

parser.add_argument(
    "--transcribers",
    type=str,
    nargs="*",
    default=[],
    choices=transcriber_choices + ["all"],
    help="The list of transcribers to benchmark",
)
parser.add_argument(
    "--agents",
    type=str,
    nargs="*",
    default=[],
    choices=agent_choices + ["all"],
    help="The list of agents to benchmark. Each agent should be of the form <company>_<model_name>.",
)
parser.add_argument(
    "--synthesizers",
    type=str,
    nargs="*",
    default=[],
    choices=synthesizer_choices + ["all"],
    help="The list of synthesizers to benchmark",
)
parser.add_argument(
    "--transcriber_audio",
    type=str,
    default="test3.wav",
    help="Path to the audio file to transcribe",
)
parser.add_argument(
    "--synthesizer_text",
    type=str,
    default="Alice was beginning to get very tired of sitting by her sister on the bank, and of having nothing to do: once or twice she had peeped into the book her sister was reading, but it had no pictures or conversations in it, “and what is the use of a book,” thought Alice “without pictures or conversations?”",
    help="The text for synthesizers to synthesize",
)
parser.add_argument(
    "--agent_prompt_preamble",
    type=str,
    default="The AI is having a very short and pleasant conversation about life",
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
parser.add_argument(
    "--results_file",
    type=str,
    default="benchmark_results.json",
    help="The file to save the benchmark JSON results to",
)
parser.add_argument(
    "--results_dir",
    type=str,
    default="benchmark_results",
    help="The directory to save the text-to-speech output and JSON results to",
)
args = parser.parse_args()
if args.all:
    print("--all is set! Running all supported transcribers, agents, and synthesizers.")
    args.transcribers = transcriber_choices
    args.agents = agent_choices
    args.synthesizers = synthesizer_choices

if "all" in args.transcribers:
    args.transcribers = transcriber_choices
if "all" in args.agents:
    args.agents = agent_choices
if "all" in args.synthesizers:
    args.synthesizers = synthesizer_choices

os.makedirs(args.results_dir, exist_ok=True)


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
        agent.attach_transcript(Transcript())
        agent_task = agent.start()
        message = AgentInput(
            transcription=Transcription(
                message=args.agent_first_input, confidence=1.0, is_final=True
            ),
            conversation_id=0,
        )
        await agent.input_queue.put(InterruptibleEvent(message))

        length_meter = meter.create_counter(
            f"agent.agent_chat_{company}-{model_name}.total_characters"
        )
        while True:
            try:
                message = await asyncio.wait_for(agent.output_queue.get(), timeout=15)
                length_meter.add(len(message.payload.message.text))
                logger.debug(
                    f"[Agent: {agent_name}] Response from API: {message.payload.message.text}"
                )
            except asyncio.TimeoutError:
                logger.debug(f"[Agent: {agent_name}] Agent queue is empty, stopping...")
                break


async def run_synthesizers():
    def create_file_output_device(synthesizer_name):
        return FileOutputDevice(
            os.path.join(args.results_dir, f"{synthesizer_name}.wav"),
        )

    for synthesizer_name in args.synthesizers:
        file_output = create_file_output_device(synthesizer_name)
        synthesizer_class, synthesizer_config_class = synthesizer_classes[
            synthesizer_name
        ]
        extra_config = {}
        if synthesizer_name == "playht":
            extra_config["voice_id"] = "larry"
        elif synthesizer_name == "rime":
            extra_config["speaker"] = "young_male_unmarked-1"
        synthesizer = synthesizer_class(
            synthesizer_config_class.from_output_device(file_output, **extra_config)
        )

        chunk_size = get_chunk_size_per_second(
            synthesizer.get_synthesizer_config().audio_encoding,
            synthesizer.get_synthesizer_config().sampling_rate,
        )

        current_synthesizer_is_streaming = synthesizer_name in STREAMING_SYNTHESIZERS
        if current_synthesizer_is_streaming:
            total_synthesis_span = tracer.start_span(
                f"synthesizer.{synthesizer_name}.create_total"
            )
            first_synthesis_span = tracer.start_span(
                f"synthesizer.{synthesizer_name}.create_first"
            )

        try:
            synthesis_result = await synthesizer.create_speech(
                message=BaseMessage(text=args.synthesizer_text), chunk_size=chunk_size
            )
        except asyncio.TimeoutError:
            logger.error(
                f"[Synthesizer: {synthesizer_name}] Timed out while synthesizing. Skipping {synthesizer_name}..."
            )
            continue
        except Exception as e:
            logger.error(
                f"[Synthesizer: {synthesizer_name}] Exception while synthesizing: {e}. Skipping {synthesizer_name}..."
            )
            continue
        chunk_generator = synthesis_result.chunk_generator

        with tqdm(desc=f"{synthesizer_name.title()} Synthesizing") as pbar:
            first_chunk = True
            while True:
                pbar.update(1)
                chunk_result = await chunk_generator.__anext__()
                if current_synthesizer_is_streaming and first_chunk:
                    first_chunk = False
                    first_synthesis_span.end()
                file_output.consume_nonblocking(chunk_result.chunk)
                if chunk_result.is_last_chunk:
                    break

        if current_synthesizer_is_streaming:
            total_synthesis_span.end()


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
    if args.synthesizers:
        await run_synthesizers()

    trace_results = span_exporter.get_finished_spans()
    final_spans = {}
    for span in trace_results:
        duration_ns = span.end_time - span.start_time
        duration_s = duration_ns / 1e9
        assert span.name not in final_spans, f"Duplicate span name: {span.name}"
        final_spans[span.name] = duration_s

    scope_metrics = reader.get_metrics_data().resource_metrics[0].scope_metrics
    if len(scope_metrics) > 0:
        metric_results = scope_metrics[0].metrics
        metric_results = {
            metric.name: metric.data.data_points[0] for metric in metric_results
        }
        final_metrics = {}
        for metric_name, raw_metric in metric_results.items():
            if re.match(r"transcriber.*\.min_latency", metric_name):
                final_metrics[metric_name] = raw_metric.min
            if re.match(r"transcriber.*\.max_latency", metric_name):
                final_metrics[metric_name] = raw_metric.max
            if re.match(r"transcriber.*\.avg_latency", metric_name):
                transcriber_str = metric_name.split(".")[1]
                final_metrics[metric_name] = (
                    raw_metric.sum
                    / metric_results[f"transcriber.{transcriber_str}.duration"].sum
                )
            if re.match(r"agent.*\.total_characters", metric_name):
                agent_str = metric_name.split(".")[1]
                final_metrics[f"agent.{agent_str}.characters_per_second"] = (
                    raw_metric.value / final_spans[f"agent.{agent_str}.generate_total"]
                )

        final_results = {**final_spans, **final_metrics}
    else:
        final_results = final_spans
    print(json.dumps(final_results, indent=4))
    if args.results_file:
        with open(os.path.join(args.results_dir, args.results_file), "w") as f:
            json.dump(final_results, f, indent=4)


if __name__ == "__main__":
    asyncio.run(main())
