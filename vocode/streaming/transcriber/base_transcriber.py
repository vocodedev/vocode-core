import asyncio
import audioop
from typing import Union
from vocode.streaming.models.audio_encoding import AudioEncoding

from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.utils.worker import AsyncWorker, AsyncQueueType, ThreadAsyncWorker


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


class AbstractTranscriber:
    def __init__(self, transcriber_config: TranscriberConfig):
        self.transcriber_config = transcriber_config
        self.is_muted = False

    def mute(self):
        self.is_muted = True

    def unmute(self):
        self.is_muted = False

    def get_transcriber_config(self) -> TranscriberConfig:
        return self.transcriber_config

    async def ready(self):
        return True

    def create_silent_chunk(self, chunk_size, sample_width=2):
        linear_audio = b"\0" * chunk_size
        if self.get_transcriber_config().audio_encoding == AudioEncoding.LINEAR16:
            return linear_audio
        elif self.get_transcriber_config().audio_encoding == AudioEncoding.MULAW:
            return audioop.lin2ulaw(linear_audio, sample_width)


class BaseAsyncTranscriber(AsyncWorker, AbstractTranscriber):
    def __init__(
        self,
        transcriber_config: TranscriberConfig,
    ):
        self.input_queue: AsyncQueueType[bytes] = asyncio.Queue()
        self.output_queue: AsyncQueueType[Transcription] = asyncio.Queue()
        self.transcriber_config = transcriber_config
        AsyncWorker.__init__(self, self.input_queue, self.output_queue)
        AbstractTranscriber.__init__(self, transcriber_config)

    async def _run_loop(self):
        raise NotImplementedError

    def send_audio(self, chunk):
        if not self.is_muted:
            self.send_nonblocking(chunk)
        else:
            self.send_nonblocking(self.create_silent_chunk(len(chunk)))

    def terminate(self):
        AsyncWorker.terminate(self)


class BaseThreadAsyncTranscriber(ThreadAsyncWorker, AbstractTranscriber):
    def __init__(
        self,
        transcriber_config: TranscriberConfig,
    ):
        self.input_queue: AsyncQueueType[bytes] = asyncio.Queue()
        self.output_queue: AsyncQueueType[Transcription] = asyncio.Queue()
        ThreadAsyncWorker.__init__(self, self.input_queue, self.output_queue)
        AbstractTranscriber.__init__(self, transcriber_config)

    def _run_loop(self):
        raise NotImplementedError

    def send_audio(self, chunk):
        if not self.is_muted:
            self.send_nonblocking(chunk)
        else:
            self.send_nonblocking(self.create_silent_chunk(len(chunk)))

    def terminate(self):
        ThreadAsyncWorker.terminate(self)


BaseTranscriber = Union[BaseAsyncTranscriber, BaseThreadAsyncTranscriber]
