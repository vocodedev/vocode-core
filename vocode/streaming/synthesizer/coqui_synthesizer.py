import io
from typing import Optional
import aiohttp
from pydub import AudioSegment

from vocode import getenv
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
)
from vocode.streaming.models.synthesizer import CoquiSynthesizerConfig, SynthesizerType
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage

from opentelemetry.context.context import Context


COQUI_BASE_URL = "https://app.coqui.ai/api/v2/"


class CoquiSynthesizer(BaseSynthesizer[CoquiSynthesizerConfig]):
    def __init__(self, synthesizer_config: CoquiSynthesizerConfig):
        super().__init__(synthesizer_config)
        self.api_key = synthesizer_config.api_key or getenv("COQUI_API_KEY")
        self.voice_id = synthesizer_config.voice_id
        self.voice_prompt = synthesizer_config.voice_prompt

    @tracer.start_as_current_span(
        "synthesis", Context(synthesizer=SynthesizerType.COQUI.value)
    )
    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        url = COQUI_BASE_URL + "samples"
        if self.voice_prompt:
            url = f"{url}/from-prompt/"

        headers = {"Authorization": f"Bearer {self.api_key}"}

        emotion = "Neutral"
        if bot_sentiment is not None and bot_sentiment.emotion:
            emotion = bot_sentiment.emotion.capitalize()

        body = {
            "text": message.text,
            "name": "unnamed",
            "emotion": emotion,
        }

        if self.voice_prompt:
            body["prompt"] = self.voice_prompt
        if self.voice_id:
            body["voice_id"] = self.voice_id

        async with aiohttp.ClientSession() as session:
            async with session.request(
                "POST",
                url,
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                sample = await response.json()
                async with session.request(
                    "GET",
                    sample["audio_url"],
                ) as response:
                    audio_segment: AudioSegment = AudioSegment.from_wav(
                        io.BytesIO(await response.read())  # type: ignore
                    )

                    output_bytes: bytes = audio_segment.raw_data

                    return self.create_synthesis_result_from_wav(
                        file=output_bytes,
                        message=message,
                        chunk_size=chunk_size,
                    )
