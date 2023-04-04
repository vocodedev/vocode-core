import io
from typing import Optional
from pydub import AudioSegment
import requests
from vocode import getenv
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer

ELEVEN_LABS_BASE_URL = "https://api.elevenlabs.io/v1/"


class ElevenLabsSynthesizer(BaseSynthesizer):
    def __init__(
        self,
        voice_id: str,
        stability: Optional[float] = None,
        similarity_boost: Optional[float] = None,
        api_key: Optional[str] = None,
    ):
        self.voice_id = voice_id
        self.api_key = getenv("ELEVEN_LABS_API_KEY", api_key)
        self.validate_stability_and_similarity_boost(stability, similarity_boost)
        self.stability = stability
        self.similarity_boost = similarity_boost

    def validate_stability_and_similarity_boost(
        self, stability: Optional[float], similarity_boost: Optional[float]
    ) -> None:
        if (stability is None) != (similarity_boost is None):
            raise ValueError(
                "Both stability and similarity_boost must be set or not set."
            )

    def synthesize(self, text: str) -> AudioSegment:
        url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{self.voice_id}"
        headers = {"xi-api-key": self.api_key, "voice_id": self.voice_id}
        body = {
            "text": text,
        }

        if self.stability is not None and self.similarity_boost is not None:
            body["voice_settings"] = {
                "stability": self.stability,
                "similarity_boost": self.similarity_boost,
            }

        response = requests.post(url, headers=headers, json=body)
        assert response.ok, response.text
        return AudioSegment.from_mp3(io.BytesIO(response.content))
