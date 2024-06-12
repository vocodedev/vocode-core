from abc import ABC, abstractmethod
import asyncio
import time

from vocode.streaming.constants import PER_CHUNK_ALLOWANCE_SECONDS
from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.output_device.abstract_output_device import AbstractOutputDevice
from vocode.streaming.output_device.audio_chunk import AudioChunk, ChunkState
from vocode.streaming.utils import get_chunk_size_per_second
from vocode.streaming.utils.worker import InterruptibleEvent, InterruptibleWorker


class RateLimitInterruptionsOutputDevice(AbstractOutputDevice):
    def __init__(
        self,
        sampling_rate: int,
        audio_encoding: AudioEncoding,
        per_chunk_allowance_seconds: float = PER_CHUNK_ALLOWANCE_SECONDS,
    ):
        super().__init__(
            input_queue=asyncio.Queue(),
        )
        self.sampling_rate = sampling_rate
        self.audio_encoding = audio_encoding
        self.per_chunk_allowance_seconds = per_chunk_allowance_seconds

    async def _run_loop(self):
        while True:
            start_time = time.time()
            try:
                item = await self.input_queue.get()
            except asyncio.CancelledError:
                return

            self.interruptible_event = item
            audio_chunk = item.payload

            if item.is_interrupted():
                audio_chunk.on_interrupt()
                audio_chunk.state = ChunkState.INTERRUPTED
                continue

            speech_length_seconds = (len(audio_chunk.data)) / get_chunk_size_per_second(
                self.audio_encoding,
                self.sampling_rate,
            )
            await self.play(audio_chunk.data)
            audio_chunk.on_play()
            audio_chunk.state = ChunkState.PLAYED
            end_time = time.time()
            await asyncio.sleep(
                max(
                    speech_length_seconds
                    - (end_time - start_time)
                    - self.per_chunk_allowance_seconds,
                    0,
                ),
            )
            self.interruptible_event.is_interruptible = False

    def interrupt(self):
        """
        For conversations that use rate-limiting playback as above,
        no custom logic is needed on interrupt, because to end synthesis, all we need to do is stop sending chunks.
        """
        pass
