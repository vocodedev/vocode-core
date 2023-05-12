import asyncio

from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.utils.worker import AsyncWorker


class Transcription:
    def __init__(
        self,
        message: str,
        confidence: float,
        is_final: bool,
        is_interrupt: bool = False,
    ):
        self.message = message
        self.confidence = confidence
        self.is_final = is_final
        self.is_interrupt = is_interrupt

    def __str__(self):
        return f"Transcription({self.message}, {self.confidence}, {self.is_final})"


class BaseTranscriber(AsyncWorker):
    def __init__(
        self,
        transcriber_config: TranscriberConfig,
    ):
        self.input_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.output_queue: asyncio.Queue[Transcription] = asyncio.Queue()
        super().__init__(self.input_queue, self.output_queue)
        self.transcriber_config = transcriber_config

    def get_transcriber_config(self) -> TranscriberConfig:
        return self.transcriber_config

    async def ready(self):
        return True

    async def _run_loop(self):
        await self.run()

    async def run(self):
        pass

    def send_audio(self, chunk):
        self.send_nonblocking(chunk)

    def terminate(self):
        super().terminate()
