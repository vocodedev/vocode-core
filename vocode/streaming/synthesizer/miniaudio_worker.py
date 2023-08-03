from __future__ import annotations
import queue

from typing import Optional, Tuple
import asyncio
import miniaudio

from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.utils import convert_wav
from vocode.streaming.utils.mp3_helper import decode_mp3
from vocode.streaming.utils.worker import ThreadAsyncWorker, logger

QueueType = Tuple[Optional[bytes], bool]


class MiniaudioWorker(ThreadAsyncWorker[QueueType]):
    def __init__(
        self,
        synthesizer_config: SynthesizerConfig,
        input_queue: asyncio.Queue[QueueType],
        output_queue: asyncio.Queue[QueueType],
    ) -> None:
        super().__init__(input_queue, output_queue)
        self.synthesizer_config = synthesizer_config
        self._ended = False

    def _run_loop(self):
        current_mp3_buffer = bytearray()
        current_wav_buffer = bytearray()
        while not self._ended:
            # Get a tuple of (mp3_chunk, is_last) from the input queue
            try:
                mp3_chunk, is_last = self.input_janus_queue.sync_q.get(timeout=1)
            except queue.Empty:
                continue
            if mp3_chunk is None:
                current_mp3_buffer.clear()
                current_wav_buffer.clear()
                self.output_janus_queue.sync_q.put((None, True))
                continue
            try:
                current_mp3_buffer.extend(mp3_chunk)
                output_bytes = decode_mp3(bytes(current_mp3_buffer))
            except miniaudio.DecodeError as e:
                # How should I log this
                logger.exception("MiniaudioWorker error: " + str(e), exc_info=True)
                self.output_janus_queue.sync_q.put((None, True))
                continue
            converted_output_bytes = convert_wav(
                output_bytes,
                output_sample_rate=self.synthesizer_config.sampling_rate,
                output_encoding=self.synthesizer_config.audio_encoding,
            )
            # take the difference between the current_wav_buffer and the converted_output_bytes
            # and put the difference in the output queue
            new_bytes = converted_output_bytes[len(current_wav_buffer) :]
            # Put a tuple of (wav_chunk, is_last) in the output queue
            self.output_janus_queue.sync_q.put((new_bytes, is_last))
            current_wav_buffer.extend(new_bytes)

    def terminate(self):
        self._ended = True
        super().terminate()
