import asyncio
import hashlib
from typing import Optional

from loguru import logger

from vocode import getenv
from vocode.streaming.models.audio import AudioEncoding, SamplingRate
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import DeepgramSynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer, SynthesisResult
from vocode.streaming.utils.create_task import asyncio_create_task_with_done_error_log

DEEPGRAM_BASE_URL = "https://api.deepgram.com/v1/"
STREAMED_CHUNK_SIZE = 16000 * 2 // 4  # 1/8 of a second of 16kHz audio with 16-bit samples


class DeepgramSynthesizer(BaseSynthesizer[DeepgramSynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: DeepgramSynthesizerConfig,
    ):
        super().__init__(synthesizer_config)

        self.api_key = synthesizer_config.api_key or getenv("DEEPGRAM_API_KEY")
        assert self.api_key is not None, "API key must be set"

        self.model_name = synthesizer_config.model_name
        self.voice_name = synthesizer_config.voice_name
        self.language_code = synthesizer_config.language_code
        self.model = synthesizer_config.model
        self.words_per_minute = 150
        self.sample_rate = self.synthesizer_config.sampling_rate
        self.as_wave = False

        if self.synthesizer_config.audio_encoding == AudioEncoding.LINEAR16:
            self.encoding = "linear16"
            match self.synthesizer_config.sampling_rate:
                case SamplingRate.RATE_8000:
                    self.sample_rate = "8000"
                case SamplingRate.RATE_16000:
                    self.sample_rate = "16000"
                case SamplingRate.RATE_24000:
                    self.sample_rate = "24000"
                case SamplingRate.RATE_32000:
                    self.sample_rate = "32000"
                case SamplingRate.RATE_44100:
                    self.output_format = "44100"
                    self.upsample = SamplingRate.RATE_48000.value
                    self.sample_rate = SamplingRate.RATE_44100.value
                case SamplingRate.RATE_48000:
                    self.sample_rate = "48000"
                case _:
                    raise ValueError(
                        f"Unsupported sampling rate: {self.synthesizer_config.sampling_rate}. Deepgram only supports 8000, 16000, 24000, 32000, and 48000 Hz."
                    )
        elif self.synthesizer_config.audio_encoding == AudioEncoding.MULAW:
            self.encoding = "mulaw"
            self.sample_rate = "8000"
        else:
            raise ValueError(
                f"Unsupported audio encoding: {self.synthesizer_config.audio_encoding}"
            )

    async def create_speech_uncached(
        self,
        message: BaseMessage,
        chunk_size: int,
        is_first_text_chunk: bool = False,
        is_sole_text_chunk: bool = False,
    ) -> SynthesisResult:
        self.total_chars += len(message.text)
        container = "wav" if self.as_wave else "none"
        url = (
            DEEPGRAM_BASE_URL
            + f"speak?model={self.model}&encoding={self.encoding}&sample_rate={self.sample_rate}&container={container}"
        )

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "text": message.text,
        }

        chunk_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        asyncio_create_task_with_done_error_log(
            self.get_chunks(url, headers, body, chunk_size, chunk_queue),
        )

        return SynthesisResult(
            self.chunk_result_generator_from_queue(chunk_queue),
            lambda seconds: self.get_message_cutoff_from_voice_speed(message, seconds, 150),
        )

    @classmethod
    def get_voice_identifier(cls, synthesizer_config: DeepgramSynthesizerConfig):
        hashed_api_key = hashlib.sha256(f"{synthesizer_config.api_key}".encode("utf-8")).hexdigest()
        return ":".join(
            (
                "deepgram_synthesizer",
                hashed_api_key,
                str(synthesizer_config.voice_name),
                str(synthesizer_config.model_name),
                str(synthesizer_config.language_code),
                synthesizer_config.audio_encoding,
            )
        )

    async def get_chunks(
        self,
        url: str,
        headers: dict,
        body: dict,
        chunk_size: int,
        chunk_queue: asyncio.Queue[Optional[bytes]],
    ):
        try:
            async_client = self.async_requestor.get_client()
            stream = await async_client.send(
                async_client.build_request(
                    "POST",
                    url,
                    headers=headers,
                    json=body,
                ),
                stream=True,
            )

            if not stream.is_success:
                error = await stream.aread()
                logger.error(f"Deepgram API failed: {stream.status_code} {error.decode('utf-8')}")
                raise Exception(f"Deepgram API returned {stream.status_code} status code")
            async for chunk in stream.aiter_bytes(chunk_size):
                chunk_queue.put_nowait(chunk)
        except asyncio.CancelledError:
            pass
        finally:
            chunk_queue.put_nowait(None)  # treated as sentinel
