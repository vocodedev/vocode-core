import wave
from io import BytesIO
from typing import Literal

from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import SynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer, SynthesisResult


def create_fake_audio(message: str, synthesizer_config: SynthesizerConfig):
    file = BytesIO()
    with wave.open(file, "wb") as wave_file:
        wave_file.setnchannels(1)
        wave_file.setsampwidth(2)
        wave_file.setframerate(synthesizer_config.sampling_rate)
        wave_file.writeframes(message.encode())
    file.seek(0)
    return file


class TestSynthesizerConfig(SynthesizerConfig):
    __test__ = False

    type: Literal["synthesizer_test"] = "synthesizer_test"


class TestSynthesizer(BaseSynthesizer[TestSynthesizerConfig]):
    """Accepts text and creates a SynthesisResult containing audio data which is the same as the text as bytes."""

    __test__ = False

    def __init__(self, synthesizer_config: SynthesizerConfig):
        super().__init__(synthesizer_config)

    async def create_speech_uncached(
        self,
        message: BaseMessage,
        chunk_size: int,
        is_first_text_chunk: bool = False,
        is_sole_text_chunk: bool = False,
    ) -> SynthesisResult:
        async def chunk_generator():
            for i in range(0, len(message.text), chunk_size):
                yield SynthesisResult.ChunkResult(
                    chunk=message.text[i : i + chunk_size].encode(), is_last_chunk=False
                )

        return SynthesisResult(
            chunk_generator=chunk_generator(),
            get_message_up_to=lambda seconds: message.text,
        )

    @classmethod
    def get_voice_identifier(cls, synthesizer_config: TestSynthesizerConfig) -> str:
        return "test_voice"
