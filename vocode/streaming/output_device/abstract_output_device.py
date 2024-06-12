from abc import ABC
from vocode.streaming.output_device.audio_chunk import AudioChunk
from vocode.streaming.utils.worker import InterruptibleEvent, InterruptibleWorker


class AbstractOutputDevice(InterruptibleWorker[InterruptibleEvent[AudioChunk]], ABC):
    pass
