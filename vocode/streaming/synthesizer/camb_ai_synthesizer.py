import asyncio
import audioop
import hashlib
from typing import Optional

from loguru import logger

from vocode import getenv
from vocode.streaming.models.audio import AudioEncoding, SamplingRate
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import CambAISynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer, SynthesisResult
from vocode.streaming.utils.create_task import asyncio_create_task

CAMB_AI_SAMPLING_RATE = 24000
STREAMED_CHUNK_SIZE = CAMB_AI_SAMPLING_RATE * 2 // 4  # 1/4 second of 24kHz 16-bit audio
MIN_TEXT_LENGTH = 3
MAX_TEXT_LENGTH = 3000


class CambAISynthesizerException(Exception):
    pass


class CambAISynthesizer(BaseSynthesizer[CambAISynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: CambAISynthesizerConfig,
    ):
        super().__init__(synthesizer_config)

        self.api_key = synthesizer_config.api_key or getenv("CAMB_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Please set CAMB_API_KEY environment variable or pass it as a parameter"
            )

        self.voice_id = synthesizer_config.voice_id
        self.model = synthesizer_config.model
        self.language = synthesizer_config.language
        self.base_url = synthesizer_config.base_url
        self.speed = synthesizer_config.speed
        self.user_instructions = synthesizer_config.user_instructions
        self.words_per_minute = 150

        # CAMB AI outputs PCM_S16LE @ 24kHz - determine if resampling is needed
        self.needs_resample = synthesizer_config.sampling_rate != CAMB_AI_SAMPLING_RATE
        self.needs_mulaw = synthesizer_config.audio_encoding == AudioEncoding.MULAW

    async def create_speech_uncached(
        self,
        message: BaseMessage,
        chunk_size: int,
        is_first_text_chunk: bool = False,
        is_sole_text_chunk: bool = False,
    ) -> SynthesisResult:
        self.total_chars += len(message.text)

        # Validate text length
        text = message.text
        if len(text) < MIN_TEXT_LENGTH:
            logger.warning(
                f"CAMB AI TTS text too short ({len(text)} chars), padding with spaces"
            )
            text = text.ljust(MIN_TEXT_LENGTH)
        if len(text) > MAX_TEXT_LENGTH:
            logger.warning(
                f"CAMB AI TTS text too long ({len(text)} chars), truncating to {MAX_TEXT_LENGTH}"
            )
            text = text[:MAX_TEXT_LENGTH]

        url = f"{self.base_url}/tts-stream"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        body = {
            "text": text,
            "voice_id": self.voice_id,
            "language": self.language,
            "speech_model": self.model,
            "output_configuration": {"format": "pcm_s16le"},
        }
        if self.speed is not None:
            body["voice_settings"] = {"speed": self.speed}
        if self.user_instructions is not None:
            body["user_instructions"] = self.user_instructions

        chunk_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        asyncio_create_task(
            self.get_chunks(url, headers, body, chunk_size, chunk_queue),
        )

        return SynthesisResult(
            self.chunk_result_generator_from_queue(chunk_queue),
            lambda seconds: self.get_message_cutoff_from_voice_speed(
                message, seconds, self.words_per_minute
            ),
        )

    async def get_chunks(
        self,
        url: str,
        headers: dict,
        body: dict,
        chunk_size: int,
        chunk_queue: asyncio.Queue[Optional[bytes]],
    ):
        stream = None
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
                raise CambAISynthesizerException(
                    f"CAMB AI API returned {stream.status_code} status code: {error.decode('utf-8')}"
                )

            async for chunk in stream.aiter_bytes(chunk_size):
                if self.needs_resample:
                    chunk = self._resample_chunk(
                        chunk,
                        CAMB_AI_SAMPLING_RATE,
                        self.synthesizer_config.sampling_rate,
                    )
                if self.needs_mulaw:
                    chunk = audioop.lin2ulaw(chunk, 2)
                chunk_queue.put_nowait(chunk)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"CAMB AI TTS error: {e}", exc_info=True)
        finally:
            if stream is not None:
                await stream.aclose()
            chunk_queue.put_nowait(None)  # sentinel

    @classmethod
    def get_voice_identifier(cls, synthesizer_config: CambAISynthesizerConfig):
        hashed_api_key = hashlib.sha256(
            f"{synthesizer_config.api_key}".encode("utf-8")
        ).hexdigest()
        return ":".join(
            (
                "camb_ai",
                hashed_api_key,
                str(synthesizer_config.voice_id),
                str(synthesizer_config.model),
                str(synthesizer_config.language),
                str(synthesizer_config.speed),
                str(synthesizer_config.user_instructions or ""),
                synthesizer_config.audio_encoding,
            )
        )
