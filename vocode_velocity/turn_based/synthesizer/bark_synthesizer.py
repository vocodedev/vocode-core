import io
import logging

import numpy as np
from loguru import logger
from pydub import AudioSegment
from scipy.io.wavfile import write as write_wav

from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer


class BarkSynthesizer(BaseSynthesizer):
    def __init__(self, silent: bool = False, **kwargs) -> None:
        from bark import SAMPLE_RATE, generate_audio, preload_models

        self.SAMPLE_RATE = SAMPLE_RATE
        self.generate_audio = generate_audio
        logger = logger or logging.getLogger(__name__)
        logger.info("Loading Bark models")
        self.silent = silent
        preload_models(**kwargs)

    def synthesize(self, text: str, **kwargs) -> AudioSegment:
        logger.debug("Bark synthesizing audio")
        audio_array = self.generate_audio(text, silent=self.silent, **kwargs)
        int_audio_arr = (audio_array * np.iinfo(np.int16).max).astype(np.int16)

        audio = io.BytesIO()
        write_wav(audio, self.SAMPLE_RATE, int_audio_arr)
        audio_segment = AudioSegment.from_wav(audio)  # type: ignore

        return audio_segment
