import io
from typing import Optional, Tuple, Dict
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
        self.use_xtts = synthesizer_config.use_xtts

    def get_request(self, text: str) -> Tuple[str, Dict[str, str], Dict[str, object]]:
        url = COQUI_BASE_URL
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = {
            "text": text,
            "speed": 1,
        }

        if self.use_xtts:
            # If we have a voice prompt, use that instead of the voice ID
            if self.voice_prompt is not None:
                url = f"{COQUI_BASE_URL}/samples/xtts/render-from-prompt/"
                body["prompt"] = self.voice_prompt
            else:
                url = f"{COQUI_BASE_URL}/samples/xtts/render/"
                body["voice_id"] = self.voice_id
        else:
            if self.voice_prompt is not None:
                url = f"{COQUI_BASE_URL}/samples/from-prompt/"
                body["prompt"] = self.voice_prompt
            else:
                url = f"{COQUI_BASE_URL}/samples"
                body["voice_id"] = self.voice_id
        return url, headers, body

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        url, headers, body = self.get_request(message.text)

        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.COQUI.value.split('_', 1)[-1]}.create_total"
        )
        async with self.aiohttp_session.request(
            "POST",
            url,
            json=body,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            sample = await response.json()
            async with self.aiohttp_session.request(
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
