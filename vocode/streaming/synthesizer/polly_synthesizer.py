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

        # AWS Polly supports sampling rate of 8k and 16k for pcm output
        if synthesizer_config.sampling_rate not in [8000, 16000]:
            raise Exception(
                "Sampling rate not supported by AWS Polly",
                synthesizer_config.sampling_rate,
            )

        self.sampling_rate = synthesizer_config.sampling_rate
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
            OutputFormat="pcm",
            VoiceId=self.voice_id,
            SampleRate=str(self.sampling_rate),
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
        response = await asyncio.get_event_loop().run_in_executor(
            self.thread_pool_executor, self.synthesize, message.text
        )
        audio_stream = response.get("AudioStream")
        create_speech_span.end()

        async def chunk_generator(audio_data_stream, chunk_transform=lambda x: x):
            audio_buffer = await asyncio.get_event_loop().run_in_executor(
                self.thread_pool_executor,
                lambda: audio_stream.read(chunk_size),
            )
            if len(audio_buffer) != chunk_size:
                yield SynthesisResult.ChunkResult(chunk_transform(audio_buffer), True)
                return
            else:
                yield SynthesisResult.ChunkResult(chunk_transform(audio_buffer), False)
            while True:
                audio_buffer = audio_stream.read(chunk_size)
                if len(audio_buffer) != chunk_size:
                    yield SynthesisResult.ChunkResult(
                        chunk_transform(audio_buffer[: len(audio_buffer)]), True
                    )
                    break
                yield SynthesisResult.ChunkResult(chunk_transform(audio_buffer), False)

        if self.synthesizer_config.should_encode_as_wav:
            output_generator = chunk_generator(
                audio_stream,
                lambda chunk: encode_as_wav(chunk, self.synthesizer_config),
            )
        else:
            output_generator = chunk_generator(audio_stream)

        return SynthesisResult(
            output_generator,
            lambda seconds: self.get_message_cutoff_from_total_response_length(
                message, seconds, len(output_bytes)
            ),
        )
