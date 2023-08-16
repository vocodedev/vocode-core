import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import Any, Optional
import aiohttp

from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
)
from vocode.streaming.models.synthesizer import PollySynthesizerConfig, SynthesizerType
from vocode.streaming.utils.mp3_helper import decode_mp3

import boto3

class PollySynthesizer(BaseSynthesizer[PollySynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: PollySynthesizerConfig,
        logger: Optional[logging.Logger] = None,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(synthesizer_config, aiohttp_session)

        client = boto3.client("polly")

        self.client = client
        self.language_code = synthesizer_config.language_code
        self.voice_id = synthesizer_config.voice_id
        self.thread_pool_executor = ThreadPoolExecutor(max_workers=1)

    def synthesize(self, message: str) -> Any:
        # Perform the text-to-speech request on the text input with the selected
        # voice parameters and audio file type
        return self.client.synthesize_speech(
            Text=message, 
            LanguageCode=self.language_code,
            TextType="text", 
            OutputFormat="mp3",
            VoiceId=self.voice_id, 
        )

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.POLLY.value.split('_', 1)[-1]}.create_total",
        )
        response = (
            await asyncio.get_event_loop().run_in_executor(
                self.thread_pool_executor, self.synthesize, message.text
            )
        )
        audio_data = response.get("AudioStream").read()
        create_speech_span.end()
        convert_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.POLLY.value.split('_', 1)[-1]}.convert",
        )
        output_bytes_io = decode_mp3(audio_data)

        result = self.create_synthesis_result_from_wav(
            file=output_bytes_io,
            message=message,
            chunk_size=chunk_size,
        )
        convert_span.end()
        return result
