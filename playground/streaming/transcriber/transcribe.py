import argparse

from vocode.streaming.input_device.microphone_input import MicrophoneInput
from vocode.streaming.models.transcriber import (
    DeepgramTranscriberConfig,
    PunctuationEndpointingConfig,
)
from vocode.streaming.transcriber.base_transcriber import BaseTranscriber, Transcription
from vocode.streaming.transcriber import *


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trace", action="store_true", help="Log latencies and other statistics"
    )
    args = parser.parse_args()

    if args.trace:
        from opentelemetry import metrics
        from opentelemetry.sdk.metrics import MeterProvider
        from playground.streaming.tracing_utils import SpecificStatisticsReader

        reader = SpecificStatisticsReader()
        provider = MeterProvider(metric_readers=[reader])
        metrics.set_meter_provider(provider)

    async def print_output(transcriber: BaseTranscriber):
        while True:
            transcription: Transcription = await transcriber.output_queue.get()
            print(transcription)

    async def listen():
        microphone_input = MicrophoneInput.from_default_device()

        # replace with the transcriber you want to test
        transcriber = DeepgramTranscriber(
            DeepgramTranscriberConfig.from_input_device(
                microphone_input, endpointing_config=PunctuationEndpointingConfig()
            )
        )
        transcriber.start()
        asyncio.create_task(print_output(transcriber))
        print("Start speaking...press Ctrl+C to end. ")
        while True:
            chunk = await microphone_input.get_audio()
            transcriber.send_audio(chunk)

    asyncio.run(listen())
