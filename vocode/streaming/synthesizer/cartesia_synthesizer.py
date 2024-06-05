import logging
import aiohttp
import wave
import numpy as np
from cartesia.tts import AsyncCartesiaTTS
from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage

from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
)

from typing import Any, Optional
import io

from vocode.streaming.models.synthesizer import CartesiaSynthesizerConfig, SynthesizerType

from opentelemetry.context.context import Context


class CartesiaSynthesizer(BaseSynthesizer[CartesiaSynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: CartesiaSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(synthesizer_config, aiohttp_session)
        self.api_key = getenv("CARTESIA_API_KEY")
        self.model_id = synthesizer_config.model_id
        self.voice_id = synthesizer_config.voice_id
        self.client = AsyncCartesiaTTS(api_key=self.api_key)
        self.voice_embedding = self.client.get_voice_embedding(voice_id=self.voice_id)

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.CARTESIA.value.split('_', 1)[-1]}.create_total",
        )
        output = await self.client.generate(
            transcript=message.text,
            voice=self.voice_embedding,
            stream=False,
            model_id=self.model_id,
            data_rtype='bytes',
            output_format='pcm'
        )
        create_speech_span.end()
        convert_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.CARTESIA.value.split('_', 1)[-1]}.convert",
        )
        
        raw_data = output['audio']
        sample_rate = output['sampling_rate']
        audio_file = io.BytesIO()

        with wave.open(audio_file, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(raw_data)
        audio_file.seek(0)

        result = self.create_synthesis_result_from_wav(
            synthesizer_config=self.synthesizer_config,
            file=audio_file,
            message=message,
            chunk_size=chunk_size,
        )
        convert_span.end()
        return result
