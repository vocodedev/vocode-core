from typing import List, Tuple, Union
import sounddevice as sd
from vocode.streaming.input_device.microphone_input import (
    MicrophoneInput as StreamingMicrophoneInput,
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


def create_microphone_input_and_speaker_output(
    streaming: bool = True,
    use_default_devices=False,
    mic_sampling_rate=None,
    speaker_sampling_rate=None,
) -> Union[
    Tuple[StreamingMicrophoneInput, StreamingSpeakerOutput],
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
    microphone_class = (
        StreamingMicrophoneInput if streaming else TurnBasedMicrophoneInput
    )
    speaker_class = StreamingSpeakerOutput if streaming else TurnBasedSpeakerOutput

    microphone_input = microphone_class(
        input_device_info, sampling_rate=mic_sampling_rate
    )
    logger.info("Using speaker output device: %s", output_device_info["name"])
    speaker_output = speaker_class(
        output_device_info, sampling_rate=speaker_sampling_rate
    )
    return microphone_input, speaker_output

class LatencyType(Enum):
    TRANSCRIPTION = "transcription"
    AGENT = "agent"
    SYNTHESIS = "synthesis"

class LatencyManager:
    def __init__(self):
        self.latencies = {
            latency_type: [] for latency_type in LatencyType
        }
        self.averages = {}
    
    def measure_latency(self, latency_type, func, *args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        latency = time.time() - start_time
        self.add_latency(latency_type, latency)
        return result

    def add_latency(self, latency_type, latency):
        self.latencies[latency_type].append(latency)

    def get_latency(self, latency_type):
        return self.latencies[latency_type][-1]

    def calculate_average_latency(self, latency_type):
        latencies = self.latencies[latency_type]
        if not latencies:
            return 0.0
        return sum(latencies) / len(latencies)

    def calculate_average_latencies(self):
        averages = {}
        for latency_type in self.latencies:
            average_latency = self.calculate_average_latency(latency_type)
            averages[latency_type] = average_latency
        self.averages = averages
        return averages
    
    def calculate_total_average_latencies(self):
        if not self.averages:
            self.calculate_average_latencies()
        return sum(self.averages.values()) / len(self.averages)
        
        
        
