import io
import logging
from typing import Optional
from pydub import AudioSegment

import requests
from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import PlayHtSynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
)

TTS_ENDPOINT = "https://play.ht/api/v2/tts/stream"


class PlayHtSynthesizer(BaseSynthesizer):
    def __init__(
        self,
        synthesizer_config: PlayHtSynthesizerConfig,
        api_key: str = None,
        user_id: str = None,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(synthesizer_config)
        self.synthesizer_config = synthesizer_config
        self.api_key = api_key or getenv("PLAY_HT_API_KEY")
        self.user_id = user_id or getenv("PLAY_HT_USER_ID")
        if not self.api_key or not self.user_id:
            raise ValueError(
                "You must set the PLAY_HT_API_KEY and PLAY_HT_USER_ID environment variables"
            )

    def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-User-ID": self.user_id,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        body = {
            "voice": self.synthesizer_config.voice_id,
            "text": message.text,
            "sample_rate": self.synthesizer_config.sampling_rate,
        }
        if self.synthesizer_config.speed:
            body["speed"] = self.synthesizer_config.speed
        if self.synthesizer_config.preset:
            body["preset"] = self.synthesizer_config.preset
        print(body)

        response = requests.post(TTS_ENDPOINT, headers=headers, json=body, timeout=5)
        if not response.ok:
            raise Exception(
                f"Play.ht API error: {response.status_code}, {response.text}"
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
