import io
from typing import Optional
from pydub import AudioSegment
from vocode import getenv
import numpy

from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer
from vocode.streaming.utils.hidden_prints import HiddenPrints
from TTS.api import TTS


class CoquiTtsSynthesizer(BaseSynthesizer):
    def __init__(self, model_name: str, speaker: Optional[str] = None, language: Optional[str] = None):
        self.model_name = model_name
        self.speaker = speaker
        self.language = language

    def synthesize(self, text) -> AudioSegment:
        tts = TTS(self.model_name)
        audio_data = numpy.array(tts.tts(text, self.speaker, self.language))

        # Convert the NumPy array to bytes
        audio_data_bytes = (audio_data * 32767).astype(numpy.int16).tobytes()

        # Create an in-memory file-like object (BytesIO) to store the audio data
        buffer = io.BytesIO(audio_data_bytes)

        # Create an AudioSegment from the buffer and set the appropriate frame rate, channels, and sample width
        return AudioSegment.from_raw(buffer, frame_rate=22050, channels=1, sample_width=2)
