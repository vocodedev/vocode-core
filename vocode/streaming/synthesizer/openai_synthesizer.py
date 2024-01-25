import aiohttp
import logging
from typing import Optional
from openai import OpenAI
from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.synthesizer import SynthesizerType

from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult, tracer
)
from vocode.streaming.models.synthesizer import (
    OpenAISynthesizerConfig,
    SynthesizerType,
)
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.utils.mp3_helper import decode_mp3


class OpenAISynthesizer(BaseSynthesizer[OpenAISynthesizerConfig]):
    def __init__(
            self,
            synthesizer_config: OpenAISynthesizerConfig,
            logger: Optional[logging.Logger] = None,
            aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(synthesizer_config, aiohttp_session)
        self.api_key = synthesizer_config.api_key or getenv("OPENAI_API_KEY")
        self.voice = synthesizer_config.voice
        self.model = synthesizer_config.model
        self.openai_client = OpenAI(api_key=self.api_key)
        # self.synthesizer_config.sampling_rate = 24000

    async def create_speech(
            self,
            message: BaseMessage,
            chunk_size: int,
            bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.OPENAI.value.split('_', 1)[-1]}.create_total",
        )

        response = self.openai_client.audio.speech.create(
            model=self.model,
            voice=self.voice,
            input=message.text,
            # response_format='opus'
        )

        audio_data = response.read()
        create_speech_span.end()
        convert_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.OPENAI.value.split('_', 1)[-1]}.convert",
        )
        output_bytes_io = decode_mp3(audio_data)

        result = self.create_synthesis_result_from_wav(
            synthesizer_config=self.synthesizer_config,
            file=output_bytes_io,
            message=message,
            chunk_size=chunk_size,
            # chunk_size=1024,
        )
        convert_span.end()

        return result
