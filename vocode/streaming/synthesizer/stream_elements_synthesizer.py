import io
import aiohttp
from pydub import AudioSegment
import logging
from typing import Optional

import requests
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import (
    StreamElementsSynthesizerConfig,
    SynthesizerType,
)
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
)

from opentelemetry.context.context import Context


class StreamElementsSynthesizer(BaseSynthesizer[StreamElementsSynthesizerConfig]):
    TTS_ENDPOINT = "https://api.streamelements.com/kappa/v2/speech"

    def __init__(
        self,
        synthesizer_config: StreamElementsSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(synthesizer_config)
        self.voice = synthesizer_config.voice

    @tracer.start_as_current_span(
        "synthesis", Context(synthesizer=SynthesizerType.STREAM_ELEMENTS.value)
    )
    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        url_params = {
            "voice": self.voice,
            "text": message.text,
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.TTS_ENDPOINT,
                params=url_params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                audio_segment: AudioSegment = AudioSegment.from_mp3(
                    io.BytesIO(await response.read())  # type: ignore
                )
                output_bytes_io = io.BytesIO()
                audio_segment.export(output_bytes_io, format="wav")  # type: ignore
                return self.create_synthesis_result_from_wav(
                    file=output_bytes_io,
                    message=message,
                    chunk_size=chunk_size,
                )
