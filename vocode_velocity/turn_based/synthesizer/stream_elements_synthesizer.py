import io

import requests
from pydub import AudioSegment

from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer


class StreamElementsSynthesizer(BaseSynthesizer):
    def __init__(self, voice: str = "Brian"):
        self.voice = voice

    TTS_ENDPOINT = "https://api.streamelements.com/kappa/v2/speech"

    def synthesize(self, text) -> AudioSegment:
        url_params = {
            "voice": self.voice,
            "text": text,
        }
        response = requests.get(self.TTS_ENDPOINT, params=url_params)
        if not response.ok:
            raise ValueError(f"Failed to synthesize text: {text}")
        return AudioSegment.from_mp3(io.BytesIO(response.content))  # type: ignore
