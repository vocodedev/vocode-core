import asyncio
from concurrent.futures import ThreadPoolExecutor
import io
import numpy as np
import logging
from typing import Optional
from scipy.io.wavfile import write as write_wav
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
)
from vocode.streaming.models.synthesizer import BarkSynthesizerConfig, SynthesizerType
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage

from opentelemetry.context.context import Context


class BarkSynthesizer(BaseSynthesizer[BarkSynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: BarkSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        super().__init__(synthesizer_config)

        from bark import SAMPLE_RATE, generate_audio, preload_models

        self.SAMPLE_RATE = SAMPLE_RATE
        self.generate_audio = generate_audio
        self.logger = logger or logging.getLogger(__name__)
        self.logger.info("Loading Bark models")
        preload_models(**self.synthesizer_config.preload_kwargs)
        self.thread_pool_executor = ThreadPoolExecutor(max_workers=1)

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.BARK.value.split('_', 1)[-1]}.create_total",
        )
        self.logger.debug("Bark synthesizing audio")
        audio_array = await asyncio.get_event_loop().run_in_executor(
            self.thread_pool_executor,
            self.generate_audio,
            message.text,
            **self.synthesizer_config.generate_kwargs,
        )
        create_speech_span.end()
        convert_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.BARK.value.split('_', 1)[-1]}.convert",
        )
        int_audio_arr = (audio_array * np.iinfo(np.int16).max).astype(np.int16)

        output_bytes_io = io.BytesIO()
        write_wav(output_bytes_io, self.SAMPLE_RATE, int_audio_arr)

        result = self.create_synthesis_result_from_wav(
            file=output_bytes_io,
            message=message,
            chunk_size=chunk_size,
        )

        convert_span.end()
        return result
