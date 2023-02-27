import pyaudio
from .input_device.microphone_input import MicrophoneInput
from .output_device.speaker_output import SpeakerOutput
import logging

logger = logging.getLogger(__name__)

def _get_device_prompt(device_infos: list[dict]) -> str:
    return """Please select a device:
{}
Choice: """.format(
        "\n".join(f"{index}: {device['name']}" for index, device in enumerate(device_infos)))

def create_microphone_input_and_speaker_output(use_first_available_device=False, mic_sampling_rate=None, speaker_sampling_rate=None) -> tuple[MicrophoneInput, SpeakerOutput]:
    pa = pyaudio.PyAudio()
    num_devices = pa.get_device_count()
    devices = list(map(pa.get_device_info_by_index, range(num_devices)))
    input_device_infos = list(filter(lambda device: device['maxInputChannels'] > 0, devices))
    output_device_infos = list(filter(lambda device: device['maxOutputChannels'] > 0, devices))
    if use_first_available_device:
        input_device_info = input_device_infos[0]
        output_device_info = output_device_infos[0]
    else:
        input_device_info = input_device_infos[int(input(_get_device_prompt(input_device_infos)))]
        output_device_info = output_device_infos[int(input(_get_device_prompt(output_device_infos)))]
    logger.info("Using microphone input device: %s", input_device_info['name'])
    microphone_input = MicrophoneInput(pa, input_device_info, sampling_rate=mic_sampling_rate)
    logger.info("Using speaker output device: %s", output_device_info['name'])
    speaker_output = SpeakerOutput(pa, output_device_info, sampling_rate=speaker_sampling_rate) 
    return microphone_input, speaker_output