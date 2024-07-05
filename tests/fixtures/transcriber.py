import asyncio

from vocode.streaming.models.transcriber import TranscriberConfig
from vocode.streaming.transcriber.base_transcriber import BaseAsyncTranscriber, Transcription


class TestTranscriberConfig(TranscriberConfig, type="transcriber_test"):
    __test__ = False


class TestAsyncTranscriber(BaseAsyncTranscriber[TestTranscriberConfig]):
    """Accepts fake audio chunks and sends out transcriptions which are the same as the audio chunks."""

    __test__ = False

    async def _run_loop(self):
        while True:
            try:
                audio_chunk = await self._input_queue.get()
                self.produce_nonblocking(
                    Transcription(message=audio_chunk.decode("utf-8"), confidence=1, is_final=True)
                )
            except asyncio.CancelledError:
                return
