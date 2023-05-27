import io
from typing import Optional, List
import aiohttp
from pydub import AudioSegment
import asyncio
import re
import logging
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
DEFAULT_SPEAKER_ID = "d2bd7ccb-1b65-4005-9578-32c4e02d8ddf"
MAX_TEXT_LENGTH = 250 # The maximum length of text that can be synthesized at once


class CoquiSynthesizer(BaseSynthesizer[CoquiSynthesizerConfig]):
    def __init__(self, synthesizer_config: CoquiSynthesizerConfig, logger: Optional[logging.Logger] = None,):
        super().__init__(synthesizer_config)
        self.api_key = synthesizer_config.api_key or getenv("COQUI_API_KEY")
        self.voice_id = synthesizer_config.voice_id
        self.voice_prompt = synthesizer_config.voice_prompt
        self.xtts = synthesizer_config.xtts # A boolean flag to indicate if xtts is enabled

    def get_request(self, text: str, bot_sentiment: Optional[BotSentiment]):
        
        # This method is similar to the one in the old class, but it adds a condition to check if xtts is enabled
        
        url = COQUI_BASE_URL
        
        if self.xtts:
            url += "samples/xtts" # Use the xtts endpoint instead of the tts one
            headers = {"Authorization": f"Bearer {self.api_key}"}
            body = {
                "text": text,
                "name": "unnamed",
            }
            
            # If we have a voice prompt, use that instead of the voice ID
            if self.voice_prompt is not None:
                url += "/render-from-prompt/"
                body["prompt"] = self.voice_prompt
            else:
                url+= "/render/"
                body["voice_id"] = self.voice_id or DEFAULT_SPEAKER_ID
                
            return url, headers, body
            
            
        else: # If xtts is not enabled, use the tts endpoint as before
            
            url += "samples"
            
            headers = {"Authorization": f"Bearer {self.api_key}"}

            emotion = "Neutral"
            if bot_sentiment is not None and bot_sentiment.emotion:
                emotion = bot_sentiment.emotion.capitalize()

            body = {
                "text": text,
                "name": "unnamed",
                "emotion": emotion,
            }

            if self.voice_prompt:
                url += "/from-prompt/"
                body["prompt"] = self.voice_prompt
            else:
                body["voice_id"] = self.voice_id or DEFAULT_SPEAKER_ID
                
            return url, headers, body

    @tracer.start_as_current_span(
        "synthesis", Context(synthesizer=SynthesizerType.COQUI.value)
    )
    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        
        # Split the text into chunks of less than MAX_TEXT_LENGTH characters
        text_chunks = self.split_text(message.text)
        
        # Create a list of tasks for each chunk using asyncio.create_task()
        tasks = [asyncio.create_task(self.async_synthesize_chunk(chunk, bot_sentiment)) for chunk in text_chunks]
        
        # Wait for all tasks to complete using asyncio.gather()
        audio_chunks = await asyncio.gather(*tasks)
        
        # Concatenate and return the results
        audio_segment = sum(audio_chunks)
        
        output_bytes = io.BytesIO(audio_segment)
        
        return self.create_synthesis_result_from_wav(
            file=output_bytes,
            message=message,
            chunk_size=chunk_size,
        )

    async def async_synthesize_chunk(self, text: str, bot_sentiment: Optional[BotSentiment]) -> aiohttp.ClientResponse:
        
        url, headers, body = self.get_request(text, bot_sentiment)

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
                    
                    return response
                    
    def split_text(self, text: str) -> List[str]:
        
        # This method is the same as the one in the old class
        
        sentence_enders = re.compile('[.!?]')
        sentences = sentence_enders.split(text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            proposed_chunk = current_chunk + sentence
            if len(proposed_chunk) > 250:
                chunks.append(current_chunk.strip())
                current_chunk = sentence + "."
            else:
                current_chunk = proposed_chunk + "."
                
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks
            
