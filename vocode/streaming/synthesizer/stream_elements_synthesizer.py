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
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(synthesizer_config, aiohttp_session)
        self.voice = synthesizer_config.voice

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
        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.STREAM_ELEMENTS.value.split('_', 1)[-1]}.create_total",
        )
        async with self.aiohttp_session.get(
            self.TTS_ENDPOINT,
            params=url_params,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            read_response = await response.read()
            create_speech_span.end()
            convert_span = tracer.start_span(
                f"synthesizer.{SynthesizerType.STREAM_ELEMENTS.value.split('_', 1)[-1]}.convert",
            )

            # TODO: probably needs to be in a thread
            audio_segment: AudioSegment = AudioSegment.from_mp3(
                io.BytesIO(read_response)  # type: ignore
            )
            output_bytes_io = io.BytesIO()
            audio_segment.export(output_bytes_io, format="wav")  # type: ignore

            result = self.create_synthesis_result_from_wav(
                file=output_bytes_io,
                message=message,
                chunk_size=chunk_size,
            )
            convert_span.end()
            return result
