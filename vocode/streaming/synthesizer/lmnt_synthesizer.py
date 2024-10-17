import asyncio
import base64
import hashlib
from typing import Optional

import aiohttp
from loguru import logger

from vocode.streaming.models.audio import AudioEncoding, SamplingRate
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import LMNTSynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer, SynthesisResult
from vocode.streaming.utils.create_task import asyncio_create_task

LMNT_BASE_URL = "https://api.lmnt.com/v1"
STREAMED_CHUNK_SIZE = 16000 * 2 // 4  # 1/8 of a second of 16kHz audio with 16-bit samples


class LMNTSynthesizer(BaseSynthesizer[LMNTSynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: LMNTSynthesizerConfig,
    ):
        super().__init__(synthesizer_config)

        assert synthesizer_config.api_key is not None, "API key must be set"
        assert synthesizer_config.voice_id is not None, "Voice ID must be set"
        self.api_key = synthesizer_config.api_key

        self.voice_id = synthesizer_config.voice_id
        self.stability = synthesizer_config.stability
        self.similarity_boost = synthesizer_config.similarity_boost
        self.sample_rate = self.synthesizer_config.sampling_rate

        if self.synthesizer_config.audio_encoding == AudioEncoding.LINEAR16:
            self.output_format = "pcm_16000"  # Update as per LMNT specifications
        elif self.synthesizer_config.audio_encoding == AudioEncoding.MULAW:
            self.output_format = "ulaw_8000"
        else:
            raise ValueError(
                f"Unsupported audio encoding: {self.synthesizer_config.audio_encoding}"
            )

        self.session = aiohttp.ClientSession()

    async def create_speech_uncached(
        self,
        message: BaseMessage,
        chunk_size: int,
        is_first_text_chunk: bool = False,
        is_sole_text_chunk: bool = False,
    ) -> SynthesisResult:
        self.total_chars += len(message.text)
        url = f"{LMNT_BASE_URL}/ai/speech"
        headers = {"X-API-Key": self.api_key}
        body = {
            "text": message.text,
            "voice": self.voice_id,
            # "stability": self.stability,
            # "similarity_boost": self.similarity_boost,
        }

        # Debugging output
        logger.debug(f"Sending request to {url} with headers {headers} and body {body}")

        # Verify that the required fields are present
        assert body["text"], "Text must not be empty"
        assert body["voice"], "Voice ID must not be empty"

        chunk_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()
        asyncio_create_task(
            self.get_chunks(url, headers, body, chunk_size, chunk_queue),
        )

        return SynthesisResult(
            self.chunk_result_generator_from_queue(chunk_queue),
            lambda seconds: self.get_message_cutoff_from_voice_speed(message, seconds, 150),
        )

    @classmethod
    def get_voice_identifier(cls, synthesizer_config: LMNTSynthesizerConfig):
        hashed_api_key = hashlib.sha256(f"{synthesizer_config.api_key}".encode("utf-8")).hexdigest()
        return ":".join(
            (
                "lmnt",
                hashed_api_key,
                str(synthesizer_config.voice_id),
                str(synthesizer_config.stability),
                str(synthesizer_config.similarity_boost),
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
            async with self.session.post(url, headers=headers, data=body) as resp:
                if resp.status != 200:
                    logger.error(f"LMNT API failed: {resp.status} {await resp.text()}")
                    raise Exception(f"LMNT API returned {resp.status} status code")

                data = await resp.json()
                audio = base64.b64decode(data["audio"])
                chunk_queue.put_nowait(audio)

        except asyncio.CancelledError:
            pass
        finally:
            chunk_queue.put_nowait(None)  # treated as sentinel

    async def close(self):
        await self.session.close()
