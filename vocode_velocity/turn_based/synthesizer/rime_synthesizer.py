import base64
import io
from typing import Optional

import requests
from pydub import AudioSegment

from vocode import getenv
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer

RIME_BASE_URL = "https://rjmopratfrdjgmfmaios.functions.supabase.co/rime-tts"


class RimeSynthesizer(BaseSynthesizer):
    def __init__(self, speaker: str, api_key: Optional[str] = None):
        self.speaker = speaker
        self.api_key = getenv("RIME_API_KEY", api_key)

    def synthesize(self, text) -> AudioSegment:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "text": text,
            "speaker": self.speaker,
        }
        response = requests.post(RIME_BASE_URL, headers=headers, json=body, timeout=5)
        audio_file = io.BytesIO(base64.b64decode(response.json().get("audioContent")))
        return AudioSegment.from_wav(audio_file)  # type: ignore
