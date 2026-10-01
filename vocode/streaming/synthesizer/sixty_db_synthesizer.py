import asyncio
import base64
import binascii
import hashlib
import io
import json
import wave
from typing import AsyncGenerator, Optional, Tuple

import aiohttp

from vocode import getenv
from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import SixtyDBSynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    encode_as_wav,
)
from vocode.streaming.telephony.constants import MULAW_SILENCE_BYTE, PCM_SILENCE_BYTE
from vocode.streaming.utils import convert_linear_audio, get_chunk_size_per_second

SOURCE_RATE = 24000
MAX_RESPONSE_BYTES = 32 * 1024 * 1024


class SixtyDBError(Exception):
    pass


class SixtyDBSynthesizer(BaseSynthesizer[SixtyDBSynthesizerConfig]):
    """Buffered REST synthesis, converted to Vocode's mono PCM16 or 8 kHz mu-law."""

    def __init__(self, synthesizer_config: SixtyDBSynthesizerConfig):
        api_key = synthesizer_config.api_key or getenv("SIXTYDB_API_KEY")
        if not api_key or not api_key.strip():
            raise ValueError("60db requires api_key or SIXTYDB_API_KEY")
        super().__init__(synthesizer_config)
        self.api_key = api_key

    @classmethod
    def get_voice_identifier(cls, synthesizer_config: SixtyDBSynthesizerConfig) -> str:
        credential = synthesizer_config.api_key or getenv("SIXTYDB_API_KEY", "")
        return ":".join(
            (
                "sixty_db",
                hashlib.sha256(credential.encode()).hexdigest(),
                synthesizer_config.base_url,
                synthesizer_config.voice_id,
                synthesizer_config.model_id,
                str(synthesizer_config.speed),
                str(synthesizer_config.sampling_rate),
                synthesizer_config.audio_encoding,
                str(synthesizer_config.should_encode_as_wav),
            )
        )

    async def create_speech_uncached(
        self,
        message: BaseMessage,
        chunk_size: int,
        is_first_text_chunk: bool = False,
        is_sole_text_chunk: bool = False,
    ) -> SynthesisResult:
        config = self.synthesizer_config
        if chunk_size <= 0 or (config.audio_encoding == AudioEncoding.LINEAR16 and chunk_size % 2):
            raise ValueError("chunk_size must be positive and aligned to the audio sample width")
        if not message.text.strip() or len(message.text) > 5000:
            raise ValueError("60db requires non-empty text of at most 5000 characters")
        self.total_chars += len(message.text)
        body = {
            "text": message.text,
            "voice_id": config.voice_id,
            "model_id": config.model_id,
            "speed": config.speed,
            "audio_config": {"audio_encoding": "LINEAR16", "sample_rate_hertz": SOURCE_RATE},
            "timestamp_type": "NONE",
        }
        async with self.async_requestor.get_session().post(
            config.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as response:
            if not response.ok:
                raise SixtyDBError(f"60db API error ({response.status})")
            data = bytearray()
            async for part in response.content.iter_chunked(65536):
                data.extend(part)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise SixtyDBError("60db response exceeds 32 MiB")
            pcm, sample_rate = decode_audio(bytes(data), response.headers.get("Content-Type", ""))
        output = convert_linear_audio(
            pcm,
            input_sample_rate=sample_rate,
            output_sample_rate=config.sampling_rate,
            output_encoding=config.audio_encoding,
        )
        if not output:
            raise SixtyDBError("60db returned empty audio")
        duration = len(output) / get_chunk_size_per_second(
            config.audio_encoding, config.sampling_rate
        )

        def get_message_up_to(seconds: Optional[float]) -> str:
            if seconds is None:
                return message.text
            return message.text[
                : max(0, min(len(message.text), int(len(message.text) * seconds / duration)))
            ]

        return SynthesisResult(self._chunk_generator(output, chunk_size), get_message_up_to)

    async def _chunk_generator(
        self, output: bytes, chunk_size: int
    ) -> AsyncGenerator[SynthesisResult.ChunkResult, None]:
        config = self.synthesizer_config
        silence = (
            MULAW_SILENCE_BYTE if config.audio_encoding == AudioEncoding.MULAW else PCM_SILENCE_BYTE
        )
        for offset in range(0, len(output), chunk_size):
            await asyncio.sleep(0)  # Keep chunk delivery cancellable without background tasks.
            chunk = output[offset : offset + chunk_size]
            is_last = offset + chunk_size >= len(output)
            if len(chunk) < chunk_size:
                chunk += silence * (chunk_size - len(chunk))
            if config.should_encode_as_wav:
                chunk = encode_as_wav(chunk, config)
            yield SynthesisResult.ChunkResult(chunk, is_last)


def decode_audio(data: bytes, content_type: str) -> Tuple[bytes, int]:
    """Decode the binary/JSON/NDJSON envelopes supported by 60db's official SDK."""
    sample_rate = SOURCE_RATE
    parts: list[bytes] = []

    def extract(value: object, depth: int = 0, wrapped: bool = False) -> None:
        nonlocal sample_rate
        if depth > 4 or not isinstance(value, dict):
            raise SixtyDBError("Invalid 60db audio envelope")
        if value.get("success") is False or value.get("type") == "error" or value.get("error"):
            raise SixtyDBError("60db synthesis failed")
        for key in ("encoding", "audio_encoding", "output_format"):
            encoding = value.get(key)
            if encoding is not None and str(encoding).lower() not in (
                "linear16",
                "pcm",
                "pcm16",
                "wav",
            ):
                raise SixtyDBError("60db must return LINEAR16 PCM or WAV audio")
        rate = value.get("sample_rate")
        if rate is not None:
            if type(rate) is not int or rate not in (16000, 24000, 48000):
                raise SixtyDBError("Invalid 60db audio sample rate")
            if parts and rate != sample_rate:
                raise SixtyDBError("60db changed sample rate within an utterance")
            sample_rate = rate
        nested = value.get("backendResponse", value.get("result"))
        if nested is not None:
            extract(nested, depth + 1, wrapped)
            return
        encoded = value.get("audio_base64", value.get("audioContent"))
        if encoded is None or encoded == "":
            return  # Metadata and timestamp records carry no audio.
        if not isinstance(encoded, str):
            raise SixtyDBError("Invalid 60db base64 audio")
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise SixtyDBError("Invalid 60db base64 audio") from error
        if decoded.lstrip().startswith(b"{"):
            try:
                inner = json.loads(decoded)
            except (ValueError, UnicodeDecodeError):
                parts.append(decoded)  # PCM samples can also start with a brace byte.
                return
            if wrapped:
                raise SixtyDBError("Too many 60db base64 audio envelopes")
            extract(inner, depth + 1, True)
        else:
            parts.append(decoded)

    mime = content_type.split(";", 1)[0].lower()
    if mime.startswith("audio/") or mime == "application/octet-stream":
        if mime not in (
            "audio/pcm",
            "audio/raw",
            "audio/linear16",
            "audio/wav",
            "audio/x-wav",
            "application/octet-stream",
        ):
            raise SixtyDBError("60db must return LINEAR16 PCM or WAV audio")
        audio = data
    else:
        try:
            try:
                extract(json.loads(data))
            except json.JSONDecodeError:
                for line in data.splitlines():
                    if line.strip():
                        extract(json.loads(line))
        except (ValueError, UnicodeDecodeError) as error:
            raise SixtyDBError("Invalid 60db JSON response") from error
        audio = b"".join(parts)
    if audio.startswith(b"RIFF"):
        try:
            with wave.open(io.BytesIO(audio), "rb") as wav:
                if (
                    wav.getnchannels() != 1
                    or wav.getsampwidth() != 2
                    or wav.getcomptype() != "NONE"
                ):
                    raise SixtyDBError("60db WAV must contain mono PCM16 audio")
                sample_rate = wav.getframerate()
                frames = wav.getnframes()
                audio = wav.readframes(frames)
                if sample_rate <= 0 or len(audio) != frames * 2:
                    raise SixtyDBError("60db WAV contains truncated or invalid PCM16 audio")
        except (wave.Error, EOFError) as error:
            raise SixtyDBError("Invalid 60db WAV audio") from error
    elif audio.startswith((b"ID3", b"OggS", b"fLaC")):
        raise SixtyDBError("60db must return LINEAR16 PCM or WAV audio")
    if not audio or len(audio) % 2:
        raise SixtyDBError("60db returned empty or incomplete PCM16 audio")
    return audio, sample_rate
