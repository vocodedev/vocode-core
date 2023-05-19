from typing import List, Tuple, Union
import typing
import sounddevice as sd
from vocode.streaming.input_device.microphone_input import (
    MicrophoneInput as StreamingMicrophoneInput,
)
from vocode.streaming.output_device.blocking_speaker_output import (
    BlockingSpeakerOutput as BlockingStreamingSpeakerOutput,
)
from vocode.streaming.output_device.speaker_output import (
    SpeakerOutput as StreamingSpeakerOutput,
)
from vocode.turn_based.input_device.microphone_input import (
    MicrophoneInput as TurnBasedMicrophoneInput,
)
from vocode.turn_based.output_device.speaker_output import (
    SpeakerOutput as TurnBasedSpeakerOutput,
)
import logging
from enum import Enum
import time

logger = logging.getLogger(__name__)


def _get_device_prompt(device_infos: List[dict]) -> str:
    return """Please select a device:
{}
Choice: """.format(
        "\n".join(
            f"{index}: {device['name']}" for index, device in enumerate(device_infos)
        )
    )


def create_streaming_microphone_input_and_speaker_output(
    use_default_devices=False,
    mic_sampling_rate=None,
    speaker_sampling_rate=None,
    use_blocking_speaker_output=False,
):
    return _create_microphone_input_and_speaker_output(
        microphone_class=StreamingMicrophoneInput,
        speaker_class=BlockingStreamingSpeakerOutput
        if use_blocking_speaker_output
        else StreamingSpeakerOutput,
        use_default_devices=use_default_devices,
        mic_sampling_rate=mic_sampling_rate,
        speaker_sampling_rate=speaker_sampling_rate,
    )


def create_turn_based_microphone_input_and_speaker_output(
    use_default_devices=False,
    mic_sampling_rate=None,
    speaker_sampling_rate=None,
):
    return _create_microphone_input_and_speaker_output(
        microphone_class=TurnBasedMicrophoneInput,
        speaker_class=TurnBasedSpeakerOutput,
        use_default_devices=use_default_devices,
        mic_sampling_rate=mic_sampling_rate,
        speaker_sampling_rate=speaker_sampling_rate,
    )


def _create_microphone_input_and_speaker_output(
    microphone_class: typing.Type[
        Union[StreamingMicrophoneInput, TurnBasedMicrophoneInput]
    ],
    speaker_class: typing.Type[
        Union[
            StreamingSpeakerOutput,
            BlockingStreamingSpeakerOutput,
            TurnBasedSpeakerOutput,
        ]
    ],
    use_default_devices=False,
    mic_sampling_rate=None,
    speaker_sampling_rate=None,
) -> Union[
    Tuple[
        StreamingMicrophoneInput,
        Union[StreamingSpeakerOutput, BlockingStreamingSpeakerOutput],
    ],
    Tuple[TurnBasedMicrophoneInput, TurnBasedSpeakerOutput],
]:
    device_infos = sd.query_devices()
    input_device_infos = list(
        filter(lambda device_info: device_info["max_input_channels"] > 0, device_infos)
    )
    output_device_infos = list(
        filter(lambda device_info: device_info["max_output_channels"] > 0, device_infos)
    )
    if use_default_devices:
        input_device_info = sd.query_devices(kind="input")
        output_device_info = sd.query_devices(kind="output")
    else:
        input_device_info = input_device_infos[
            int(input(_get_device_prompt(input_device_infos)))
        ]
        output_device_info = output_device_infos[
            int(input(_get_device_prompt(output_device_infos)))
        ]
    logger.info("Using microphone input device: %s", input_device_info["name"])

    microphone_input = microphone_class(
        input_device_info, sampling_rate=mic_sampling_rate
    )
    logger.info("Using speaker output device: %s", output_device_info["name"])
    speaker_output = speaker_class(
        output_device_info, sampling_rate=speaker_sampling_rate
    )
    return microphone_input, speaker_output  # type: ignore

class LatencyType(Enum):
    TRANSCRIPTION = "transcription"
    AGENT = "agent"
    SYNTHESIS = "synthesis"
    STREAMING = "streaming"

DEFAULT_ROUNDING_DIGITS = 4

class LatencyManager:
    def __init__(self, rounding_digits: int = DEFAULT_ROUNDING_DIGITS):
        self.latencies: typing.Dict[LatencyType, List[float]] = {
            latency_type: [] for latency_type in LatencyType
        }
        self.averages: typing.Dict[LatencyType, float] = {}
        self.rounding_digits = rounding_digits
    
    def measure_latency(self, latency_type, func, *args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        latency = time.time() - start_time
        self.add_latency(latency_type, latency)
        return result

    def add_latency(self, latency_type, latency):
        latency = self.round_latency(latency)
        self.latencies[latency_type].append(latency)

    def get_latency(self, latency_type):
        return self.latencies[latency_type][-1]

    def calculate_average_latency(self, latency_type):
        latencies = self.latencies[latency_type]
        if not latencies:
            return 0.0
        return self.round_latency(sum(latencies) / len(latencies))

    def calculate_average_latencies(self):
        averages = {}
        for latency_type in self.latencies:
            if latency_type == LatencyType.STREAMING:
                continue
            average_latency = self.calculate_average_latency(latency_type)
            averages[latency_type] = average_latency
        self.averages = averages
        return averages
    
    def calculate_total_average_latencies(self):
        if not self.averages:
            self.calculate_average_latencies()
        return self.round_latency(sum(self.averages.values()) / len(self.averages))
    
    def round_latency(self, latency):
        return round(latency, self.rounding_digits)

    def log_turn_based_latencies(self, logger):
        logger.info(f"Latency - Transcription: {self.get_latency(LatencyType.TRANSCRIPTION)} seconds, Agent: {self.get_latency(LatencyType.AGENT)} seconds, Synthesis: {self.get_latency(LatencyType.SYNTHESIS)} seconds")
    
    def log_average_turn_based_latencies(self, logger):
        average_latencies = self.calculate_average_latencies()
        logger.info("\nAverage latencies:")
        for latency_type in average_latencies:
            logger.info(f"Average {latency_type.value} latency: {average_latencies[latency_type]} seconds")
        logger.info(f"Total average latency: {self.calculate_total_average_latencies()} seconds")
    
    def log_streaming_latency(self, logger):
        logger.info(f"Streaming Latency: {self.get_latency(LatencyType.STREAMING)} seconds")
    
    def log_average_streaming_latency(self, logger):
        logger.info(f"Average Streaming Latency: {self.calculate_average_latency(LatencyType.STREAMING)} seconds")
        
        
