import os
from io import BytesIO
from typing import Optional

import pytest
from tests.streaming.data.loader import get_audio_path
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
)


class TestSynthesizerConfig(SynthesizerConfig, type="synthesizer_test"):
    __test__ = False


class TestSynthesizer(BaseSynthesizer):
    __test__ = False

    def __init__(self, synthesizer_config: SynthesizerConfig):
        super().__init__(synthesizer_config)

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        return self.create_synthesis_result_from_wav(
            message=message,
            chunk_size=chunk_size,
            file=get_audio_path("fake_audio.wav"),
        )
