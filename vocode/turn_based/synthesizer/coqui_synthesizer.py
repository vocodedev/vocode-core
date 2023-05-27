import io
import re
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
        xtts: bool = False,
        api_key: Optional[str] = None,
    ):
        self.voice_id = voice_id or DEFAULT_SPEAKER_ID
        self.voice_prompt = voice_prompt
        self.xtts = xtts
        self.api_key = getenv("COQUI_API_KEY", api_key)

    def synthesize(self, text: str) -> AudioSegment:
        # Split the text into chunks of less than MAX_TEXT_LENGTH characters
        text_chunks = self.split_text(text)
        # Synthesize each chunk and concatenate the results
        audio_chunks = [self.synthesize_chunk(chunk) for chunk in text_chunks]
        return sum(audio_chunks) # type: ignore

    def synthesize_chunk(self, text: str) -> AudioSegment:
        url, headers, body = self.get_request(text)

        # Get the sample
        response = requests.post(url, headers=headers, json=body)
        assert response.ok, response.text
        sample = response.json()
        response = requests.get(sample["audio_url"])
        return AudioSegment.from_wav(io.BytesIO(response.content))  # type: ignore

    def split_text(self, text: str) -> List[str]:
        sentence_enders = re.compile('[.!?]')
        # Split the text into sentences using the regular expression
        sentences = sentence_enders.split(text)
        chunks = []
        current_chunk = ""
        for sentence in sentences:
            # Strip leading and trailing whitespace from the sentence
            sentence = sentence.strip()
            # If the sentence is empty, skip it
            if not sentence:
                continue
            # Concatenate the current chunk and the sentence, and add a period to the end
            proposed_chunk = current_chunk + sentence
            if len(proposed_chunk) > 250:
                chunks.append(current_chunk.strip())
                current_chunk = sentence + "."
            else:
                current_chunk = proposed_chunk + "."
        # If there is a current chunk at the end, add it to the list of chunks
        if current_chunk:
            chunks.append(current_chunk.strip())
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
                assert response.status == 201, await response.text() + url + str(headers) + str(body)
                sample = await response.json()
                audio_url = sample["audio_url"]

                # Get the audio data asynchronously using await
                async with session.get(audio_url) as response:
                    assert response.status == 200, "Coqui audio download failed"
                    audio_data = await response.read()

                    # Return an AudioSegment object from the audio data
                    return AudioSegment.from_wav(io.BytesIO(audio_data))  # type: ignore

    def get_request(self, text: str) -> tuple[str, dict[str, str], dict[str, str]]:
        url = COQUI_BASE_URL
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "application/json"}
        body = {
            "text": text,
            "speed": 1,
        }

        if self.xtts:
            # If we have a voice prompt, use that instead of the voice ID
            if self.voice_prompt is not None:
                url += "samples/xtts/render-from-prompt/"
                body["prompt"] = self.voice_prompt
            else:
                url += "samples/xtts/render/"
                body["voice_id"] = self.voice_id
        else:
            if self.voice_prompt is not None:
                url += "samples/from-prompt/"
                body["prompt"] = self.voice_prompt
            else:
                url += "samples"
                body["voice_id"] = self.voice_id
        return url, headers, body
