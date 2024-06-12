from abc import abstractmethod
import asyncio
from vocode.streaming.output_device.audio_chunk import AudioChunk
from vocode.streaming.utils.worker import AbstractAsyncWorker, InterruptibleEvent


class AbstractOutputDevice(AbstractAsyncWorker[InterruptibleEvent[AudioChunk]]):

    def __init__(self, sampling_rate: int, audio_encoding):
        super().__init__(input_queue=asyncio.Queue())
        self.sampling_rate = sampling_rate
        self.audio_encoding = audio_encoding

    @abstractmethod
    async def play(self, chunk: bytes):
        pass

    @abstractmethod
    def interrupt(self):
        pass
