import io
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
    def __init__(self, config: ElevenLabsSynthesizerConfig):
        super().__init__(config)
        self.api_key = config.api_key or getenv("ELEVEN_LABS_API_KEY")
        self.voice_id = config.voice_id or ADAM_VOICE_ID
        self.words_per_minute = 150

    def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{self.voice_id}"
        headers = {"xi-api-key": self.api_key, "voice_id": self.voice_id}
        body = {
            "text": message.text,
        }
        response = requests.post(url, headers=headers, json=body, timeout=5)

        audio_segment: AudioSegment = AudioSegment.from_mp3(
            io.BytesIO(response.content)
        )

        output_bytes_io = io.BytesIO()
        audio_segment.export(output_bytes_io, format="wav")

        if self.synthesizer_config.audio_encoding == AudioEncoding.LINEAR16:
            output_bytes = convert_wav(
                output_bytes_io,
                output_sample_rate=self.synthesizer_config.sampling_rate,
                output_encoding=AudioEncoding.LINEAR16,
            )
        elif self.synthesizer_config.audio_encoding == AudioEncoding.MULAW:
            output_bytes = convert_wav(
                output_bytes_io,
                output_sample_rate=self.synthesizer_config.sampling_rate,
                output_encoding=AudioEncoding.MULAW,
            )

        if self.synthesizer_config.should_encode_as_wav:
            output_bytes = encode_as_wav(output_bytes)

        def chunk_generator(output_bytes):
            for i in range(0, len(output_bytes), chunk_size):
                if i + chunk_size > len(output_bytes):
                    yield SynthesisResult.ChunkResult(output_bytes[i:], True)
                else:
                    yield SynthesisResult.ChunkResult(
                        output_bytes[i : i + chunk_size], False
                    )

        return SynthesisResult(
            chunk_generator(output_bytes),
            lambda seconds: self.get_message_cutoff_from_total_response_length(
                message, seconds, len(output_bytes)
            ),
        )
