import asyncio

import pytest
from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.transcriber.base_transcriber import (
    BaseAsyncTranscriber,
    Transcription,
)


class TestTranscriberConfig(TranscriberConfig, type="transcriber_test"):
    __test__ = False


class TestAsyncTranscriber(BaseAsyncTranscriber):
    __test__ = False

    async def _run_loop(self):
        while True:
            try:
                self.output_queue.put_nowait(
                    Transcription(message="test", confidence=1, is_final=True)
                )
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                return
