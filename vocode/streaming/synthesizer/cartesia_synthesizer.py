import hashlib
import io
import wave

from vocode import getenv
from vocode.streaming.models.audio import AudioEncoding, SamplingRate
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import CartesiaSynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer, SynthesisResult


class CartesiaSynthesizer(BaseSynthesizer[CartesiaSynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: CartesiaSynthesizerConfig,
    ):
        super().__init__(synthesizer_config)

        # Lazy import the cartesia module
        try:
            from cartesia import AsyncCartesia
        except ImportError as e:
            raise ImportError(f"Missing required dependancies for CartesiaSynthesizer") from e

        self.api_key = synthesizer_config.api_key or getenv("CARTESIA_API_KEY")
        if not self.api_key:
            raise ValueError("Missing Cartesia API key")

        self.cartesia_tts = AsyncCartesia

        if synthesizer_config.audio_encoding == AudioEncoding.LINEAR16:
            match synthesizer_config.sampling_rate:
                case SamplingRate.RATE_44100:
                    self.output_format = {
                        "sample_rate": 44100,
                        "encoding": "pcm_s16le",
                        "container": "raw",
                    }
                case SamplingRate.RATE_22050:
                    self.output_format = {
                        "sample_rate": 22050,
                        "encoding": "pcm_s16le",
                        "container": "raw",
                    }
                case SamplingRate.RATE_16000:
                    self.output_format = {
                        "sample_rate": 16000,
                        "encoding": "pcm_s16le",
                        "container": "raw",
                    }
                case SamplingRate.RATE_8000:
                    self.output_format = {
                        "sample_rate": 8000,
                        "encoding": "pcm_s16le",
                        "container": "raw",
                    }
                case _:
                    raise ValueError(
                        f"Unsupported PCM sampling rate {synthesizer_config.sampling_rate}"
                    )
        elif synthesizer_config.audio_encoding == AudioEncoding.MULAW:
            self.channel_width = 2
            self.output_format = {
                "sample_rate": 8000,
                "encoding": "pcm_mulaw",
                "container": "raw",
            }
        else:
            raise ValueError(f"Unsupported audio encoding {synthesizer_config.audio_encoding}")

        if not isinstance(self.output_format["sample_rate"], int):
            raise ValueError(f"Invalid type for sample_rate")
        self.sampling_rate = self.output_format["sample_rate"]
        self.num_channels = 1
        self.model_id = synthesizer_config.model_id
        self.voice_id = synthesizer_config.voice_id
        self.client = self.cartesia_tts(api_key=self.api_key)

    async def create_speech_uncached(
        self,
        message: BaseMessage,
        chunk_size: int,
        is_first_text_chunk: bool = False,
        is_sole_text_chunk: bool = False,
    ) -> SynthesisResult:
        generator = await self.client.tts.sse(
            model_id=self.model_id,
            transcript=message.text,
            voice_id=self.voice_id,
            stream=True,
            output_format=self.output_format,
        )

        async def chunk_generator(sse):
            buffer = bytearray()
            async for event in sse:
                audio = event.get("audio")
                buffer.extend(audio)
                while len(buffer) >= chunk_size:
                    yield SynthesisResult.ChunkResult(
                        chunk=buffer[:chunk_size], is_last_chunk=False
                    )
                    buffer = buffer[chunk_size:]
            yield SynthesisResult.ChunkResult(chunk=buffer, is_last_chunk=True)

        return SynthesisResult(
            chunk_generator=chunk_generator(generator),
            get_message_up_to=lambda seconds: self.get_message_cutoff_from_voice_speed(
                message, seconds
            ),
        )

    @classmethod
    def get_voice_identifier(cls, synthesizer_config: CartesiaSynthesizerConfig):
        hashed_api_key = hashlib.sha256(f"{synthesizer_config.api_key}".encode("utf-8")).hexdigest()
        return ":".join(
            (
                "cartesia",
                hashed_api_key,
                str(synthesizer_config.voice_id),
                str(synthesizer_config.model_id),
                synthesizer_config.audio_encoding,
            )
        )

    async def tear_down(self):
        await super().tear_down()
        await self.client.close()
