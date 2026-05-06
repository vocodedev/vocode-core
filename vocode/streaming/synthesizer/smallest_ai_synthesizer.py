import asyncio
import audioop
import base64
import hashlib
from typing import Optional

import aiohttp
from loguru import logger

from vocode import getenv
from vocode.streaming.models.audio import AudioEncoding, SamplingRate
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import SmallestAISynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer, SynthesisResult
from vocode.streaming.utils.create_task import asyncio_create_task

SMALLEST_AI_BASE_URL = "https://waves-api.smallest.ai/api/v1"


class SmallestAIError(Exception):
    pass


class SmallestAISynthesizer(BaseSynthesizer[SmallestAISynthesizerConfig]):
    def __init__(self, synthesizer_config: SmallestAISynthesizerConfig):
        super().__init__(synthesizer_config)
        self.api_key = synthesizer_config.api_key or getenv("SMALLEST_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Missing Smallest AI API key. Set SMALLEST_API_KEY env var or pass api_key."
            )
        self.voice_id = synthesizer_config.voice_id
        self.model = synthesizer_config.model
        self.speed = synthesizer_config.speed
        self.consistency = synthesizer_config.consistency
        self.similarity = synthesizer_config.similarity
        self.enhancement = synthesizer_config.enhancement

        if synthesizer_config.audio_encoding == AudioEncoding.LINEAR16:
            self.sample_rate = synthesizer_config.sampling_rate
        elif synthesizer_config.audio_encoding == AudioEncoding.MULAW:
            # Smallest AI doesn't natively output MULAW; generate PCM at 8kHz then convert
            self.sample_rate = SamplingRate.RATE_8000.value
        else:
            raise ValueError(f"Unsupported audio encoding: {synthesizer_config.audio_encoding}")

    @classmethod
    def get_voice_identifier(cls, synthesizer_config: SmallestAISynthesizerConfig):
        hashed_key = hashlib.sha256(
            f"{synthesizer_config.api_key}".encode("utf-8")
        ).hexdigest()
        return ":".join(
            (
                "smallest_ai",
                hashed_key,
                str(synthesizer_config.voice_id),
                str(synthesizer_config.model),
                str(synthesizer_config.speed),
                synthesizer_config.audio_encoding,
            )
        )

    def _get_url(self) -> str:
        return f"{SMALLEST_AI_BASE_URL}/{self.model}/get_speech"

    def _build_body(self, text: str) -> dict:
        body: dict = {
            "text": text,
            "voice_id": self.voice_id,
            "sample_rate": self.sample_rate,
            "speed": self.speed,
            "add_wav_header": False,
        }
        if self.model == "lightning-large":
            body["consistency"] = self.consistency
            body["similarity"] = self.similarity
            body["enhancement"] = self.enhancement
        return body

    async def create_speech_uncached(
        self,
        message: BaseMessage,
        chunk_size: int,
        is_first_text_chunk: bool = False,
        is_sole_text_chunk: bool = False,
    ) -> SynthesisResult:
        self.total_chars += len(message.text)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = self._build_body(message.text)
        chunk_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        asyncio_create_task(self._stream_chunks(headers, body, chunk_size, chunk_queue))
        return SynthesisResult(
            self.chunk_result_generator_from_queue(chunk_queue),
            lambda seconds: self.get_message_cutoff_from_voice_speed(message, seconds, 150),
        )

    async def _stream_chunks(
        self,
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
                    self._get_url(),
                    headers=headers,
                    json=body,
                ),
                stream=True,
            )
            if not stream.is_success:
                error = await stream.aread()
                raise SmallestAIError(
                    f"Smallest AI TTS API returned {stream.status_code}: {error.decode('utf-8')}"
                )

            # The API returns SSE: lines like "data: <base64-encoded-pcm>"
            buffer = bytearray()
            async for line in stream.aiter_lines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    pcm_chunk = base64.b64decode(payload)
                except Exception:
                    # Raw bytes response (non-SSE fallback)
                    pcm_chunk = payload.encode("latin-1")

                if self.synthesizer_config.audio_encoding == AudioEncoding.MULAW:
                    pcm_chunk = audioop.lin2ulaw(pcm_chunk, 2)

                buffer.extend(pcm_chunk)
                while len(buffer) >= chunk_size:
                    chunk_queue.put_nowait(bytes(buffer[:chunk_size]))
                    buffer = buffer[chunk_size:]

            if buffer:
                chunk_queue.put_nowait(bytes(buffer))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"SmallestAISynthesizer error: {e}")
        finally:
            chunk_queue.put_nowait(None)
