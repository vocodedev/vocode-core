import io
import logging
from typing import Any, Optional
import requests
from pydub import AudioSegment

from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.utils import convert_wav

from vocode import getenv
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    encode_as_wav,
)
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage


ELEVEN_LABS_BASE_URL = "https://api.elevenlabs.io/v1/"
ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"


class ElevenLabsSynthesizer(BaseSynthesizer):
    def __init__(
        self,
        config: ElevenLabsSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(config)
        self.api_key = config.api_key or getenv("ELEVEN_LABS_API_KEY")
        self.voice_id = config.voice_id or ADAM_VOICE_ID
        self.stability = config.stability
        self.similarity_boost = config.similarity_boost
        self.words_per_minute = 150
        

    def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{self.voice_id}"
        headers = {"xi-api-key": self.api_key, "voice_id": self.voice_id}
        body = {"text": message.text}

        if self.stability is not None and self.similarity_boost is not None:
            body["voice_settings"] = {
                "stability": self.stability,
                "similarity_boost": self.similarity_boost,
            }


        response = requests.post(url, headers=headers, json=body, timeout=5)
        if not response.ok:
            raise ValueError(
                f"Eleven Labs API error: {response.status_code} - {response.text}"
            )


        audio_segment: AudioSegment = AudioSegment.from_mp3(
            io.BytesIO(response.content)
        )

        output_bytes_io = io.BytesIO()

        audio_segment.export(output_bytes_io, format="wav")

        return self.create_synthesis_result_from_wav(
            file=output_bytes_io,
            message=message,
            chunk_size=chunk_size,
        )
