import io
from typing import Optional, List
from pydub import AudioSegment
import requests
from vocode import getenv
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer
import aiohttp
import asyncio

COQUI_BASE_URL = "https://app.coqui.ai/api/v2/"
DEFAULT_SPEAKER_ID = "d2bd7ccb-1b65-4005-9578-32c4e02d8ddf"
MAX_TEXT_LENGTH = 250  # The maximum length of text that can be synthesized at once


class CoquiSynthesizer(BaseSynthesizer):
    def __init__(
        self,
        voice_id: Optional[str] = None,
        voice_prompt: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.voice_id = voice_id or DEFAULT_SPEAKER_ID
        self.voice_prompt = voice_prompt
        self.api_key = getenv("COQUI_API_KEY", api_key)

    def synthesize(self, text: str) -> AudioSegment:
        # Split the text into chunks of less than MAX_TEXT_LENGTH characters
        text_chunks = self.split_text(text)
        # Synthesize each chunk and concatenate the results
        audio_chunks = [self.synthesize_chunk(chunk) for chunk in text_chunks]
        return sum(audio_chunks)

    def synthesize_chunk(self, text: str) -> AudioSegment:
        url, headers, body = self.get_request(text)

        # Get the sample
        response = requests.post(url, headers=headers, json=body)
        assert response.ok, response.text
        sample = response.json()
        response = requests.get(sample["audio_url"])
        return AudioSegment.from_wav(io.BytesIO(response.content))  # type: ignore

    def split_text(self, text: str) -> List[str]:
        # This method splits a long text into smaller chunks of less than 250 characters
        # It tries to preserve the sentence boundaries and avoid splitting words
        chunks = []
        start = 0
        end = MAX_TEXT_LENGTH
        while start < len(text):
            # Find the last space or punctuation before the end position
            while end > start and end < len(text) and not (text[end] in ".?!"):
                end -= 1
            # If no space or punctuation is found, just split at the end position
            if end == start:
                end = start + MAX_TEXT_LENGTH
            # Add the chunk to the list and update the start and end positions
            chunks.append(text[start:end])
            start = end
            end = min(start + MAX_TEXT_LENGTH, len(text))
        return chunks

    async def async_synthesize(self, text: str) -> AudioSegment:
        # This method is similar to the synthesize method, but it uses async IO to synthesize each chunk in parallel

        # Split the text into chunks of less than MAX_TEXT_LENGTH characters
        text_chunks = self.split_text(text)

        # Create a list of tasks for each chunk using asyncio.create_task()
        tasks = [
            asyncio.create_task(self.async_synthesize_chunk(chunk))
            for chunk in text_chunks
        ]

        # Wait for all tasks to complete using asyncio.gather()
        audio_chunks = await asyncio.gather(*tasks)

        # Concatenate and return the results
        return sum(audio_chunks)

    async def async_synthesize_chunk(self, text: str) -> AudioSegment:
        url, headers, body = self.get_request(text)

        # Create an aiohttp session and post the request asynchronously using await
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body) as response:
                assert response.status == 201, await response.text()
                sample = await response.json()
                audio_url = sample["audio_url"]

                # Get the audio data asynchronously using await
                async with session.get(audio_url) as response:
                    assert response.status == 200, "Coqui audio download failed"
                    audio_data = await response.read()

                    # Return an AudioSegment object from the audio data
                    return AudioSegment.from_wav(io.BytesIO(audio_data))  # type: ignore

    def get_request(self, text: str):
        url = COQUI_BASE_URL
        headers = {"Authorization": f"Bearer {self.api_key}"}
        body = {
            "text": text,
            "name": "unnamed",
        }

        # If we have a voice prompt, use that instead of the voice ID
        if self.voice_prompt is not None:
            url += "samples/from-prompt/"
            body["prompt"] = self.voice_prompt
        else:
            url += "samples"
            body["speaker_id"] = self.voice_id
        return url, headers, body
