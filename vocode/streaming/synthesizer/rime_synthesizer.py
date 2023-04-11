import audioop
import logging
from pydub import AudioSegment
import base64
from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.message import BaseMessage

from .base_synthesizer import BaseSynthesizer, SynthesisResult, encode_as_wav
from typing import Any, Optional
import os
import io
from dotenv import load_dotenv
import requests

from vocode.streaming.models.synthesizer import RimeSynthesizerConfig

load_dotenv()

# https://rime.ai/docs/quickstart
RIME_SAMPLING_RATE = 22050
RIME_BASE_URL = "https://rjmopratfrdjgmfmaios.functions.supabase.co/rime-tts"


class RimeSynthesizer(BaseSynthesizer):
    def __init__(
        self, config: RimeSynthesizerConfig, logger: Optional[logging.Logger] = None
    ):
        super().__init__(config)
        self.api_key = getenv("RIME_API_KEY")
        self.speaker = config.speaker

    def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "text": message.text,
            "speaker": self.speaker,
        }
        response = requests.post(RIME_BASE_URL, headers=headers, json=body, timeout=5)
        if not response.ok:
            raise Exception(f"Rime API error: {response.status_code}, {response.text}")
        audio_file = io.BytesIO(base64.b64decode(response.json().get("audioContent")))

        return self.create_synthesis_result_from_wav(
            file=audio_file, message=message, chunk_size=chunk_size
        )
