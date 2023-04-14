import io
from pydub import AudioSegment
import logging
from typing import Optional

import requests
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import StreamElementsSynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
)


class StreamElementsSynthesizer(BaseSynthesizer):
    TTS_ENDPOINT = "https://api.streamelements.com/kappa/v2/speech"

    def __init__(
        self,
        config: StreamElementsSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(config)
        self.voice = config.voice

    def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        url_params = {
            "voice": self.voice,
            "text": message.text,
        }
        response = requests.get(self.TTS_ENDPOINT, params=url_params)
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
