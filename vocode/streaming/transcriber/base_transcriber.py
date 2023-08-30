from __future__ import annotations

import asyncio
import audioop
from typing import Generic, TypeVar, Union
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.model import BaseModel

from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.utils.worker import AsyncWorker, ThreadAsyncWorker


class Transcription(BaseModel):
    message: str
    confidence: float
    is_final: bool
    is_interrupt: bool = False
    offset: float = 0
    duration: float = 0

    def __str__(self):
        return f"Transcription({self.message}, {self.confidence}, {self.is_final})"


TranscriberConfigType = TypeVar("TranscriberConfigType", bound=TranscriberConfig)


class AbstractTranscriber(Generic[TranscriberConfigType]):
    def __init__(self, transcriber_config: TranscriberConfigType):
        self.transcriber_config = transcriber_config
        self.is_muted = False

    def mute(self):
        self.is_muted = True

    def unmute(self):
        self.is_muted = False

    def get_transcriber_config(self) -> TranscriberConfigType:
        return self.transcriber_config

    async def ready(self):
        return True

    def create_silent_chunk(self, chunk_size, sample_width=2):
        linear_audio = b"\0" * chunk_size
        if self.get_transcriber_config().audio_encoding == AudioEncoding.LINEAR16:
            return linear_audio
        elif self.get_transcriber_config().audio_encoding == AudioEncoding.MULAW:
            return audioop.lin2ulaw(linear_audio, sample_width)

    def trim_audio(
        self,
        audio_buffer: bytearray,
        total_bytes: int,
        offset_s: float,
        duration_s: float,
    ):
        """
        Extracts / trims an audio buffer to match the given offset and duration.

        Args:
            audio_buffer: The audio buffer. May have been truncated, e.g. length may be < total_bytes
            total_bytes: The total number of bytes recorded since starting the stream
            offset_s: The offset in seconds since start of stream, to start trimming from
            duration_s: The duration in seconds to trim
        """

        offset_bytes = int(offset_s * 2 * self.transcriber_config.sampling_rate)
        duration_bytes = int(duration_s * 2 * self.transcriber_config.sampling_rate)
        
        if offset_bytes + duration_bytes > total_bytes:
            duration_bytes = total_bytes - offset_bytes
        # We may have truncated the audio buffer since start of streaming so we need to 
        # adjust the offset in bytes to match up with the truncated buffer
        offset_bytes -= total_bytes
        offset_bytes += len(audio_buffer)
        offset_bytes = max(0, offset_bytes)
        # Ensure we have a minimum duration
        if (duration_bytes == 0) or (
            len(audio_buffer) <= (2 * self.transcriber_config.sampling_rate)
        ):
            trimmed_audio = audio_buffer
        else:
            trimmed_audio = audio_buffer[offset_bytes : offset_bytes + duration_bytes]
        return trimmed_audio


class BaseAsyncTranscriber(AbstractTranscriber[TranscriberConfigType], AsyncWorker):
    def __init__(
        self,
        transcriber_config: TranscriberConfigType,
    ):
        self.input_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.output_queue: asyncio.Queue[Transcription] = asyncio.Queue()
        AsyncWorker.__init__(self, self.input_queue, self.output_queue)
        AbstractTranscriber.__init__(self, transcriber_config)

    async def _run_loop(self):
        raise NotImplementedError

    def send_audio(self, chunk):
        if not self.is_muted:
            self.consume_nonblocking(chunk)
        else:
            self.consume_nonblocking(self.create_silent_chunk(len(chunk)))

    def terminate(self):
        AsyncWorker.terminate(self)


class BaseThreadAsyncTranscriber(
    AbstractTranscriber[TranscriberConfigType], ThreadAsyncWorker
):
    def __init__(
        self,
        transcriber_config: TranscriberConfigType,
    ):
        self.input_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.output_queue: asyncio.Queue[Transcription] = asyncio.Queue()
        ThreadAsyncWorker.__init__(self, self.input_queue, self.output_queue)
        AbstractTranscriber.__init__(self, transcriber_config)

    def _run_loop(self):
        raise NotImplementedError

    def send_audio(self, chunk):
        if not self.is_muted:
            self.consume_nonblocking(chunk)
        else:
            self.consume_nonblocking(self.create_silent_chunk(len(chunk)))

    def terminate(self):
        ThreadAsyncWorker.terminate(self)


BaseTranscriber = Union[
    BaseAsyncTranscriber[TranscriberConfigType],
    BaseThreadAsyncTranscriber[TranscriberConfigType],
]
