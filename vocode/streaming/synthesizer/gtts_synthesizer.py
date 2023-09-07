import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import aiohttp
from pydub import AudioSegment
from typing import Optional
from io import BytesIO
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import GTTSSynthesizerConfig, SynthesizerType
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
)

from opentelemetry.context.context import Context


class GTTSSynthesizer(BaseSynthesizer):
    def __init__(
        self,
        synthesizer_config: GTTSSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(synthesizer_config, aiohttp_session)

        from gtts import gTTS

        self.gTTS = gTTS
        self.thread_pool_executor = ThreadPoolExecutor(max_workers=1)

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        audio_file = BytesIO()

        def thread():
            tts = self.gTTS(message.text)
            tts.write_to_fp(audio_file)

        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.GTTS.value.split('_', 1)[-1]}.create_total"
        )
        await asyncio.get_event_loop().run_in_executor(
            self.thread_pool_executor, thread
        )
        create_speech_span.end()
        convert_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.GTTS.value.split('_', 1)[-1]}.convert",
        )
        audio_file.seek(0)
        # TODO: probably needs to be in a thread
        audio_segment: AudioSegment = AudioSegment.from_mp3(audio_file)  # type: ignore
        output_bytes_io = BytesIO()
        audio_segment.export(output_bytes_io, format="wav")  # type: ignore

        result = self.create_synthesis_result_from_wav(
            file=output_bytes_io,
            message=message,
            chunk_size=chunk_size,
        )
        convert_span.end()
        return result
