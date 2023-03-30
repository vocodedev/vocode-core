import io
from typing import Optional
import requests
from pydub import AudioSegment

from vocode import getenv
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
)
from vocode.streaming.models.synthesizer import CoquiSynthesizerConfig
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage


COQUI_BASE_URL = "https://app.coqui.ai/api/v2/"
DEFAULT_SPEAKER_ID = "d2bd7ccb-1b65-4005-9578-32c4e02d8ddf"


class CoquiSynthesizer(BaseSynthesizer):
    def __init__(self, config: CoquiSynthesizerConfig):
        super().__init__(config)
        self.api_key = config.api_key or getenv("COQUI_API_KEY")
        self.voice_id = config.voice_id or DEFAULT_SPEAKER_ID

    def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        url = COQUI_BASE_URL + "samples"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        emotion = "Neutral"
        if bot_sentiment.emotion:
            emotion = bot_sentiment.emotion.capitalize()
        body = {
            "text": message.text,
            "speaker_id": self.voice_id,
            "name": "unnamed",
            "emotion": emotion,
        }
        # print("➡️", body)
        response = requests.post(url, headers=headers, json=body, timeout=5)
        sample = response.json()
        # print("⬅️", sample)
        response = requests.get(sample["audio_url"])
        audio_segment: AudioSegment = AudioSegment.from_wav(
            io.BytesIO(response.content)
        )

        output_bytes: bytes = audio_segment.raw_data

        self.create_synthesis_result_from_wav(
            file=output_bytes,
            message=message,
            chunk_size=chunk_size,
        )
