import asyncio
import io
import logging
from typing import Optional
from aiohttp import ClientSession, ClientTimeout
from pydub import AudioSegment

import requests
from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import PlayHtSynthesizerConfig, SynthesizerType
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
)

from opentelemetry.context.context import Context

TTS_ENDPOINT = "https://play.ht/api/v2/tts/stream"


class PlayHtSynthesizer(BaseSynthesizer[PlayHtSynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: PlayHtSynthesizerConfig,
        api_key: Optional[str] = None,
        user_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        aiohttp_session: Optional[ClientSession] = None,
    ):
        print(api_key, user_id)
        super().__init__(synthesizer_config, aiohttp_session)
        self.synthesizer_config = synthesizer_config
        self.api_key = api_key or getenv("PLAY_HT_API_KEY")
        self.user_id = user_id or getenv("PLAY_HT_USER_ID")
        if not self.api_key or not self.user_id:
            raise ValueError(
                "You must set the PLAY_HT_API_KEY and PLAY_HT_USER_ID environment variables"
            )

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-User-ID": self.user_id,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        body = {
            "voice": self.synthesizer_config.voice_id,
            "text": message.text,
            "quality": self.synthesizer_config.quality,
            "output_format": self.synthesizer_config.output_format,
            "sample_rate": self.synthesizer_config.sampling_rate,
        }
        if self.synthesizer_config.speed:
            body["speed"] = self.synthesizer_config.speed
        if self.synthesizer_config.seed:
            body["seed"] = self.synthesizer_config.seed
        if self.synthesizer_config.temperature:
            body["temperature"] = self.synthesizer_config.temperature

        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.PLAY_HT.value.split('_', 1)[-1]}.create_total",
        )

        async with self.aiohttp_session.post(
            TTS_ENDPOINT,
            headers=headers,
            json=body,
            timeout=ClientTimeout(total=15)
        ) as response:
            if not response.ok:
                raise Exception(
                    f"Play.ht API error status code {response.status}"
                )
            read_response = await response.read()
            create_speech_span.end()
            convert_span = tracer.start_span(
                f"synthesizer.{SynthesizerType.PLAY_HT.value.split('_', 1)[-1]}.convert",
            )
            # Run the conversion from MP3 in a separate thread
            loop = asyncio.get_event_loop()
            audio_segment = await loop.run_in_executor(
                None, lambda: AudioSegment.from_mp3(io.BytesIO(read_response))  # type: ignore
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
