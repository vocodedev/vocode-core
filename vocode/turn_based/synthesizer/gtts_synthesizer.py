from io import BytesIO
from os import PathLike
from typing import Any

from pydub import AudioSegment

from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer


class GTTSSynthesizer(BaseSynthesizer):
    def __init__(self):
        from gtts import gTTS

        self.gTTS = gTTS

    def synthesize(self, text) -> AudioSegment:
        tts = self.gTTS(text)
        audio_file = BytesIO()
        tts.write_to_fp(audio_file)
        audio_file.seek(0)
        return AudioSegment.from_mp3(audio_file)  # type: ignore
