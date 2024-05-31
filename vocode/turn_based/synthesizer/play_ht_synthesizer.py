import io
from typing import Optional

import requests
from pydub import AudioSegment

from vocode import getenv
from vocode.streaming.models.audio import SamplingRate
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer

DEFAULT_SAMPLING_RATE = SamplingRate.RATE_24000
TTS_ENDPOINT = "https://play.ht/api/v2/tts/stream"


class PlayHtSynthesizer(BaseSynthesizer):
    def __init__(
        self,
        voice: str,
        sample_rate: int = DEFAULT_SAMPLING_RATE,
        speed: Optional[float] = None,
        preset: Optional[str] = None,
        api_key: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.voice = voice
        self.sample_rate = sample_rate
        self.speed = speed
        self.preset = preset
        self.api_key = getenv("PLAY_HT_API_KEY", api_key)
        self.user_id = getenv("PLAY_HT_USER_ID", user_id)

    def synthesize(
        self,
        text: str,
    ) -> AudioSegment:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-User-ID": self.user_id,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        body = {
            "voice": self.voice,
            "text": text,
            "sample_rate": self.sample_rate,
        }
        if self.speed is not None:
            body["speed"] = self.speed
        if self.preset is not None:
            body["preset"] = self.preset

        response = requests.post(TTS_ENDPOINT, headers=headers, json=body, timeout=5)
        if not response.ok:
            raise Exception(f"Play.ht API error: {response.status_code}, {response.text}")

        return AudioSegment.from_mp3(io.BytesIO(response.content))  # type: ignore
