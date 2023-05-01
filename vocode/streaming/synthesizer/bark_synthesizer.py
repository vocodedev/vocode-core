import io
import numpy as np
import logging
from typing import Optional
from scipy.io.wavfile import write as write_wav
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
)
from vocode.streaming.models.synthesizer import BarkSynthesizerConfig
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage


class BarkSynthesizer(BaseSynthesizer):
    def __init__(
        self, config: BarkSynthesizerConfig, logger: logging.Logger = None
    ) -> None:
        super().__init__(config)

        from bark import SAMPLE_RATE, generate_audio, preload_models

        self.SAMPLE_RATE = SAMPLE_RATE
        self.generate_audio = generate_audio
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.logger.info("Loading Bark models")
        preload_models(**self.config.preload_kwargs)

    def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        self.logger.debug("Bark synthesizing audio")
        audio_array = self.generate_audio(message.text, **self.config.generate_kwargs)
        int_audio_arr = (audio_array * np.iinfo(np.int16).max).astype(np.int16)

        output_bytes_io = io.BytesIO()
        write_wav(output_bytes_io, self.SAMPLE_RATE, int_audio_arr)

        return self.create_synthesis_result_from_wav(
            file=output_bytes_io,
            message=message,
            chunk_size=chunk_size,
        )
