import io
from typing import Optional
from pydub import AudioSegment
import requests
from vocode import getenv
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer

ELEVEN_LABS_BASE_URL = "https://api.elevenlabs.io/v1/"


class ElevenLabsSynthesizer(BaseSynthesizer):
    def __init__(self, voice_id: str, api_key: Optional[str] = None):
        self.voice_id = voice_id
        self.api_key = getenv("ELEVEN_LABS_API_KEY", api_key)

    def synthesize(self, text: str) -> AudioSegment:
        url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{self.voice_id}"
        headers = {"xi-api-key": self.api_key, "voice_id": self.voice_id}
        body = {
            "text": text,
        }
        response = requests.post(url, headers=headers, json=body)
        assert response.ok, response.text
        return AudioSegment.from_mp3(io.BytesIO(response.content))
