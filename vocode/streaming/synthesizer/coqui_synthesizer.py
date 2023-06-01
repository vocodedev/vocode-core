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


COQUI_BASE_URL = "https://app.coqui.ai/api/v2"


class CoquiSynthesizer(BaseSynthesizer[CoquiSynthesizerConfig]):
    def __init__(self, synthesizer_config: CoquiSynthesizerConfig):
        super().__init__(synthesizer_config)
        self.api_key = synthesizer_config.api_key or getenv("COQUI_API_KEY")
        self.voice_id = synthesizer_config.voice_id
        self.voice_prompt = synthesizer_config.voice_prompt

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        url = f"{COQUI_BASE_URL}/samples/xtts/render/"
        if self.voice_prompt:
            url = f"{COQUI_BASE_URL}/samples/xtts/render-from-prompt/"

        headers = {"Authorization": f"Bearer {self.api_key}"}

        body = {
            "text": message.text,
            "name": "unnamed",
        }

        if self.voice_prompt:
            body["prompt"] = self.voice_prompt
        elif self.voice_id:
            body["voice_id"] = self.voice_id

        # print("➡️", body)

        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.COQUI.value.split('_', 1)[-1]}.create_total"
        )
        async with aiohttp.ClientSession() as session:
            async with session.request(
                "POST",
                url,
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                sample = await response.json()
                # print("⬅️", sample)
                async with session.request(
                    "GET",
                    sample["audio_url"],
                ) as response:
                    read_response = await response.read()
                    create_speech_span.end()
                    convert_span = tracer.start_span(
                        f"synthesizer.{SynthesizerType.COQUI.value.split('_', 1)[-1]}.convert",
                    )

                    result = self.create_synthesis_result_from_wav(
                        file=io.BytesIO(read_response),
                        message=message,
                        chunk_size=chunk_size,
                    )
                    convert_span.end()
                    return result
