import asyncio
from abc import abstractmethod

from vocode.streaming.output_device.audio_chunk import AudioChunk
from vocode.streaming.utils.worker import AsyncWorker, InterruptibleEvent


class AbstractOutputDevice(AsyncWorker[InterruptibleEvent[AudioChunk]]):

    def __init__(self, sampling_rate: int, audio_encoding):
        super().__init__(input_queue=asyncio.Queue())
        self.sampling_rate = sampling_rate
        self.audio_encoding = audio_encoding

    @abstractmethod
    def interrupt(self):
        pass
