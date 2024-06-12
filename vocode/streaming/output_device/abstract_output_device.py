from abc import abstractmethod
from vocode.streaming.output_device.audio_chunk import AudioChunk
from vocode.streaming.utils.worker import AbstractAsyncWorker, InterruptibleEvent


class AbstractOutputDevice(AbstractAsyncWorker[InterruptibleEvent[AudioChunk]]):
    @abstractmethod
    async def play(self, chunk: bytes):
        pass

    @abstractmethod
    def interrupt(self):
        pass
