from typing import Any, Optional
import requests
from vocode import getenv

from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
)
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage


ELEVEN_LABS_BASE_URL = "https://api.elevenlabs.io/v1/"
ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
OBAMA_VOICE_ID = "vLITIS0SH2an5iQGxw5C"


class ElevenLabsSynthesizer(BaseSynthesizer):
    def __init__(self, config: ElevenLabsSynthesizerConfig):
        super().__init__(config)
        self.api_key = getenv("ELEVEN_LABS_API_KEY")
        self.voice_id = config.voice_id or ADAM_VOICE_ID
        self.words_per_minute = 150

    def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{self.voice_id}/stream"
        headers = {"xi-api-key": self.api_key, "voice_id": self.voice_id}
        body = {
            "text": message.text,
        }
        response = requests.post(url, headers=headers, json=body)

        def chunk_generator(response):
            for chunk in response.iter_content(chunk_size=chunk_size):
                yield SynthesisResult.ChunkResult(chunk, len(chunk) != chunk_size)

        assert (
            not self.synthesizer_config.should_encode_as_wav
        ), "ElevenLabs does not support WAV encoding"
        # return chunk_generator(response), lambda seconds: self.get_message_cutoff_from_voice_speed(message, seconds, self.words_per_minute)
        return SynthesisResult(chunk_generator(response), lambda seconds: message.text)
