import asyncio
import hashlib
from typing import List, Tuple

from loguru import logger

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
            raise ImportError("Missing required dependancies for CartesiaSynthesizer") from e

        self.api_key = synthesizer_config.api_key or getenv("CARTESIA_API_KEY")
        if not self.api_key:
            raise ValueError("Missing Cartesia API key")

        self.cartesia_tts = AsyncCartesia

        self._experimental_voice_controls = None
        if synthesizer_config.experimental_voice_controls:
            self._experimental_voice_controls = (
                synthesizer_config.experimental_voice_controls.dict()
            )

        if synthesizer_config.audio_encoding == AudioEncoding.LINEAR16:
            match synthesizer_config.sampling_rate:
                case SamplingRate.RATE_48000:
                    self.output_format = {
                        "sample_rate": 48000,
                        "encoding": "pcm_s16le",
                        "container": "raw",
                    }
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
            raise ValueError("Invalid type for sample_rate")
        self.sampling_rate = self.output_format["sample_rate"]
        self.num_channels = 1
        self.model_id = synthesizer_config.model_id
        self.voice_id = synthesizer_config.voice_id
        self.client = self.cartesia_tts(api_key=self.api_key)
        self.ws = None
        self.ctx = None
        self.ctx_message = BaseMessage(text="")
        self.ctx_timestamps: List[Tuple[str, float, float]] = []
        self.no_more_inputs_task = None
        self.no_more_inputs_lock = asyncio.Lock()

    async def initialize_ws(self):
        if self.ws is None:
            self.ws = await self.client.tts.websocket()

    async def initialize_ctx(self, is_first_text_chunk: bool):
        if self.ctx is None or self.ctx.is_closed():
            self.ctx_message = BaseMessage(text="")
            self.ctx_timestamps = []
            if self.ws:
                self.ctx = self.ws.context()
        else:
            if is_first_text_chunk:
                self.ctx_message = BaseMessage(text="")
                self.ctx_timestamps = []
                if self.no_more_inputs_task:
                    self.no_more_inputs_task.cancel()
                await self.ctx.no_more_inputs()
                self.ctx = self.ws.context()

    # This workaround is necessary to prevent the last chunk getting delayed.
    # In the future, `create_speech_uncached` should be modified to handle this properly by adding a flag to the last chunk.
    def refresh_no_more_inputs_task(self):
        if self.no_more_inputs_task:
            self.no_more_inputs_task.cancel()

        async def delayed_no_more_inputs():
            await asyncio.sleep(1)
            async with self.no_more_inputs_lock:
                if self.ctx:
                    await self.ctx.no_more_inputs()

        self.no_more_inputs_task = asyncio.create_task(delayed_no_more_inputs())

    async def create_speech_uncached(
        self,
        message: BaseMessage,
        chunk_size: int,
        is_first_text_chunk: bool = False,
        is_sole_text_chunk: bool = False,
    ) -> SynthesisResult:
        await self.initialize_ws()
        await self.initialize_ctx(is_first_text_chunk)

        transcript = message.text

        if not message.text.endswith(" "):
            transcript = message.text + " "

        if self.ctx is not None:
            await self.ctx.send(
                model_id=self.model_id,
                transcript=transcript,
                voice_id=self.voice_id,
                continue_=not is_sole_text_chunk,
                output_format=self.output_format,
                add_timestamps=True,
                _experimental_voice_controls=self._experimental_voice_controls,
            )
            if not is_sole_text_chunk:
                try:
                    self.refresh_no_more_inputs_task()
                except Exception as e:
                    logger.info(f"Caught error while sending no more inputs: {e}")

        async def chunk_generator(context):
            buffer = bytearray()
            if context.is_closed():
                return
            try:
                async for event in context.receive():
                    audio = event.get("audio")
                    word_timestamps = event.get("word_timestamps")
                    if word_timestamps:
                        words = word_timestamps["words"]
                        start_times = word_timestamps["start"]
                        end_times = word_timestamps["end"]
                        for word, start, end in zip(words, start_times, end_times):
                            self.ctx_timestamps.append((word, start, end))
                    if audio:
                        buffer.extend(audio)
                        while len(buffer) >= chunk_size:
                            yield SynthesisResult.ChunkResult(
                                chunk=buffer[:chunk_size], is_last_chunk=False
                            )
                            buffer = buffer[chunk_size:]
            except Exception as e:
                logger.info(
                    f"Caught error while receiving audio chunks from CartesiaSynthesizer: {e}"
                )
                self.ctx._close()
            if buffer:
                # pad the leftover buffer with silence
                if len(buffer) < chunk_size:
                    padding_size = chunk_size - len(buffer)
                    if self.output_format["encoding"] == "pcm_mulaw":
                        buffer.extend(b"\x7f" * padding_size)  # 127 is silence in mu-law
                    elif self.output_format["encoding"] == "pcm_s16le":
                        buffer.extend(b"\x00\x00" * padding_size)  # 0 is silence in s16le
                yield SynthesisResult.ChunkResult(chunk=buffer, is_last_chunk=True)

        self.ctx_message.text += transcript

        def get_message_cutoff_ctx(message, seconds, words_per_minute=150):
            if seconds:
                closest_index = 0
                if len(self.ctx_timestamps) > 0:
                    for index, word_timestamp in enumerate(self.ctx_timestamps):
                        _word, start, end = word_timestamp
                        closest_index = index
                        if end >= seconds:
                            break
                if closest_index:
                    # Check if they're less than 2 seconds apart, fall back to words per minute otherwise
                    if self.ctx_timestamps[closest_index][2] - seconds < 2:
                        return " ".join(
                            [word for word, *_ in self.ctx_timestamps[: closest_index + 1]]
                        )
            return self.get_message_cutoff_from_voice_speed(message, seconds, words_per_minute)

        return SynthesisResult(
            chunk_generator=chunk_generator(self.ctx),
            get_message_up_to=lambda seconds: get_message_cutoff_ctx(self.ctx_message, seconds),
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
        if self.no_more_inputs_task:
            self.no_more_inputs_task.cancel()
        if self.ctx:
            self.ctx._close()
        await self.ws.close()
        await self.client.close()
