import io
from typing import Optional
from pydub import AudioSegment
import requests
from vocode import getenv
from vocode.streaming.telephony.constants import DEFAULT_SAMPLING_RATE

from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer

DEFAULT_SAMPLING_RATE = 24000
TTS_ENDPOINT = "https://play.ht/api/v2/tts/stream"


class PlayHtSynthesizer(BaseSynthesizer):
    def create_speech(
        self,
        text: str,
        voice_id: str,
        sampling_rate: int = DEFAULT_SAMPLING_RATE,
        speed: Optional[float] = None,
        preset: Optional[str] = None,
        api_key: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> AudioSegment:
        api_key = api_key or getenv("PLAY_HT_API_KEY")
        user_id = user_id or getenv("PLAY_HT_USER_ID")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-User-ID": user_id,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        body = {
            "voice": voice_id,
            "text": text,
            "sample_rate": sampling_rate,
        }
        if speed is not None:
            body["speed"] = speed
        if preset is not None:
            body["preset"] = preset

        response = requests.post(TTS_ENDPOINT, headers=headers, json=body, timeout=5)
        if not response.ok:
            raise Exception(
                f"Play.ht API error: {response.status_code}, {response.text}"
            )

        return AudioSegment.from_mp3(io.BytesIO(response.content))
