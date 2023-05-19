import io
from typing import Optional
from pydub import AudioSegment
import requests
from vocode import getenv
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer

COQUI_BASE_URL = "https://app.coqui.ai/api/v2/"
DEFAULT_SPEAKER_ID = "d2bd7ccb-1b65-4005-9578-32c4e02d8ddf"


class CoquiSynthesizer(BaseSynthesizer):
    def __init__(self, voice_id: Optional[str] = None, api_key: Optional[str] = None):
        self.voice_id = voice_id or DEFAULT_SPEAKER_ID
        self.api_key = getenv("COQUI_API_KEY", api_key)

    def synthesize(self, text: str) -> AudioSegment:
        url = COQUI_BASE_URL + "samples"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        body = {
            "text": text,
            "speaker_id": self.voice_id,
            "name": "unnamed",
        }
        response = requests.post(url, headers=headers, json=body)
        assert response.ok, response.text
        sample = response.json()
        response = requests.get(sample["audio_url"])
        return AudioSegment.from_wav(io.BytesIO(response.content))  # type: ignore
