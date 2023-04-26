import logging
from pydub import AudioSegment
from typing import Optional
from io import BytesIO
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import GTTSSynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
)


class GTTSSynthesizer(BaseSynthesizer):
    def __init__(
        self,
        config: GTTSSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(config)

        from gtts import gTTS
        self.gTTS = gTTS

    def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        tts = self.gTTS(message.text)
        audio_file = BytesIO()
        tts.write_to_fp(audio_file)
        audio_file.seek(0)
        audio_segment: AudioSegment = AudioSegment.from_mp3(audio_file)
        output_bytes_io = BytesIO()
        audio_segment.export(output_bytes_io, format="wav")
        return self.create_synthesis_result_from_wav(
            file=output_bytes_io,
            message=message,
            chunk_size=chunk_size,
        )
