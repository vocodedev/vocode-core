import audioop
import base64
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.audio_encoding import AudioEncoding

from vocode.streaming.models.message import BaseMessage

from .base_synthesizer import BaseSynthesizer, SynthesisResult, encode_as_wav
from typing import Any, Optional
import os
import io
import wave
from dotenv import load_dotenv
import requests

from ..utils import convert_linear_audio, convert_wav
from ..models.synthesizer import ElevenLabsSynthesizerConfig, RimeSynthesizerConfig

load_dotenv()

RIME_API_KEY = os.getenv("RIME_API_KEY")
RIME_BASE_URL = os.getenv("RIME_BASE_URL")


class RimeSynthesizer(BaseSynthesizer):
    def __init__(self, config: RimeSynthesizerConfig):
        super().__init__(config)
        self.speaker = config.speaker

    def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        url = RIME_BASE_URL
        headers = {"Authorization": f"Bearer {RIME_API_KEY}"}
        body = {"inputs": {"text": message.text, "speaker": self.speaker}}
        response = requests.post(url, headers=headers, json=body)

        def chunk_generator(audio, chunk_transform=lambda x: x):
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i : i + chunk_size]
                yield SynthesisResult.ChunkResult(
                    chunk_transform(chunk), len(chunk) != chunk_size
                )

        assert response.ok, response.text
        data = response.json().get("data")
        assert data

        audio_file = io.BytesIO(base64.b64decode(data))

        if self.synthesizer_config.audio_encoding == AudioEncoding.LINEAR16:
            output_bytes = convert_wav(
                audio_file,
                output_sample_rate=self.synthesizer_config.sampling_rate,
                output_encoding=AudioEncoding.LINEAR16,
            )
        elif self.synthesizer_config.audio_encoding == AudioEncoding.MULAW:
            output_bytes = convert_wav(
                audio_file,
                output_sample_rate=self.synthesizer_config.sampling_rate,
                output_encoding=AudioEncoding.MULAW,
            )

        if self.synthesizer_config.should_encode_as_wav:
            output_generator = chunk_generator(
                output_bytes, chunk_transform=encode_as_wav
            )
        else:
            output_generator = chunk_generator(output_bytes)
        return SynthesisResult(
            output_generator,
            lambda seconds: self.get_message_cutoff_from_total_response_length(
                message, seconds, len(output_bytes)
            ),
        )
