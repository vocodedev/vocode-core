import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import Optional
import aiohttp
from pydub import AudioSegment
import numpy as np
import io
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.message import BaseMessage

from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
)

from vocode.streaming.models.synthesizer import (
    CoquiTTSSynthesizerConfig,
    SynthesizerType,
)

from opentelemetry.context.context import Context


class CoquiTTSSynthesizer(BaseSynthesizer[CoquiTTSSynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: CoquiTTSSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(synthesizer_config, aiohttp_session)

        from TTS.api import TTS

        self.tts = TTS(**synthesizer_config.tts_kwargs)
        self.speaker = synthesizer_config.speaker
        self.language = synthesizer_config.language
        self.thread_pool_executor = ThreadPoolExecutor(max_workers=1)

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.COQUI_TTS.value.split('_', 1)[-1]}.create_total",
        )
        tts = self.tts
        audio_data = await asyncio.get_event_loop().run_in_executor(
            self.thread_pool_executor,
            tts.tts,
            message.text,
            self.speaker,
            self.language,
        )
        create_speech_span.end()
        convert_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.COQUI_TTS.value.split('_', 1)[-1]}.convert",
        )
        audio_data = np.array(audio_data)

        # Convert the NumPy array to bytes
        audio_data_bytes = (audio_data * 32767).astype(np.int16).tobytes()

        # Create an in-memory file-like object (BytesIO) to store the audio data
        buffer = io.BytesIO(audio_data_bytes)

        audio_segment: AudioSegment = AudioSegment.from_raw(
            buffer, frame_rate=22050, channels=1, sample_width=2  # type: ignore
        )

        output_bytes_io = io.BytesIO()
        audio_segment.export(output_bytes_io, format="wav")  # type: ignore

        result = self.create_synthesis_result_from_wav(
            file=output_bytes_io, message=message, chunk_size=chunk_size
        )

        convert_span.end()
        return result
