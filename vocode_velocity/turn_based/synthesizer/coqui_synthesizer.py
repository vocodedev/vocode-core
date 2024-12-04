import asyncio
import io
import re
import typing
from typing import List, Optional

import aiohttp
import requests
from pydub import AudioSegment

from vocode import getenv
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer

raise DeprecationWarning("This Synthesizer is deprecated and will be removed in the future.")

COQUI_BASE_URL = "https://app.coqui.ai/api/v2/samples"
DEFAULT_SPEAKER_ID = "d2bd7ccb-1b65-4005-9578-32c4e02d8ddf"
MAX_TEXT_LENGTH = 250  # The maximum length of text that can be synthesized at once


class CoquiSynthesizer(BaseSynthesizer):
    def __init__(
        self,
        voice_id: Optional[str] = None,
        voice_prompt: Optional[str] = None,
        use_xtts: bool = False,
        api_key: Optional[str] = None,
    ):
        self.voice_id = voice_id or DEFAULT_SPEAKER_ID
        self.voice_prompt = voice_prompt
        self.use_xtts = use_xtts
        self.api_key = getenv("COQUI_API_KEY", api_key)

    def synthesize(self, text: str) -> AudioSegment:
        text_chunks = self.split_text(text)
        audio_chunks = [self.synthesize_chunk(chunk) for chunk in text_chunks]
        return sum(audio_chunks)  # type: ignore

    def synthesize_chunk(self, text: str) -> AudioSegment:
        url, headers, body = self.get_request(text)

        # Get the sample
        response = requests.post(url, headers=headers, json=body)
        assert response.ok, response.text
        sample = response.json()
        response = requests.get(sample["audio_url"])
        return AudioSegment.from_wav(io.BytesIO(response.content))  # type: ignore

    def split_text(self, string):
        # Base case: if the string is less than or equal to MAX_TEXT_LENGTH characters, return it as a single element array
        if len(string) <= MAX_TEXT_LENGTH:
            return [string.strip()]

        # Recursive case: find the index of the last sentence ender in the first MAX_TEXT_LENGTH characters of the string
        sentence_enders = [".", "!", "?"]
        index = -1
        for ender in sentence_enders:
            i = string[:MAX_TEXT_LENGTH].rfind(ender)
            if i > index:
                index = i

        # If there is a sentence ender, split the string at that index plus one and strip any spaces from both parts
        if index != -1:
            first_part = string[: index + 1].strip()
            second_part = string[index + 1 :].strip()

        # If there is no sentence ender, find the index of the last comma in the first MAX_TEXT_LENGTH characters of the string
        else:
            index = string[:MAX_TEXT_LENGTH].rfind(",")
            # If there is a comma, split the string at that index plus one and strip any spaces from both parts
            if index != -1:
                first_part = string[: index + 1].strip()
                second_part = string[index + 1 :].strip()

            # If there is no comma, find the index of the last space in the first MAX_TEXT_LENGTH characters of the string
            else:
                index = string[:MAX_TEXT_LENGTH].rfind(" ")
            # If there is a space, split the string at that index and strip any spaces from both parts
            if index != -1:
                first_part = string[:index].strip()
                second_part = string[index:].strip()

            # If there is no space, split the string at MAX_TEXT_LENGTH characters and strip any spaces from both parts
            else:
                first_part = string[:MAX_TEXT_LENGTH].strip()
                second_part = string[MAX_TEXT_LENGTH:].strip()

        # Append the first part to the result array
        result = [first_part]

        # Call the function recursively on the remaining part of the string and extend the result array with it, unless it is empty
        if second_part != "":
            result.extend(self.split_text(second_part))

        # Return the result array
        return result

    async def async_synthesize(self, text: str) -> AudioSegment:
        # This method is similar to the synthesize method, but it uses async IO to synthesize each chunk in parallel

        # Split the text into chunks of less than MAX_TEXT_LENGTH characters
        text_chunks = self.split_text(text)

        # Create a list of tasks for each chunk using asyncio.create_task()
        tasks = [asyncio.create_task(self.async_synthesize_chunk(chunk)) for chunk in text_chunks]

        # Wait for all tasks to complete using asyncio.gather()
        audio_chunks = await asyncio.gather(*tasks)

        # Concatenate and return the results
        return sum(audio_chunks)  # type: ignore

    async def async_synthesize_chunk(self, text: str) -> AudioSegment:
        url, headers, body = self.get_request(text)

        # Create an aiohttp session and post the request asynchronously using await
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body) as response:
                assert response.status == 201, (
                    await response.text() + url + str(headers) + str(body)
                )
                sample = await response.json()
                audio_url = sample["audio_url"]

                # Get the audio data asynchronously using await
                async with session.get(audio_url) as response:
                    assert response.status == 200, "Coqui audio download failed"
                    audio_data = await response.read()

                    # Return an AudioSegment object from the audio data
                    return AudioSegment.from_wav(io.BytesIO(audio_data))  # type: ignore

    def get_request(
        self, text: str
    ) -> typing.Tuple[str, typing.Dict[str, str], typing.Dict[str, object]]:
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
            url += "/xtts/"
            # If we have a voice prompt, use that instead of the voice ID
            if self.voice_prompt is not None:
                url += "render-from-prompt/"
                body["prompt"] = self.voice_prompt
            else:
                url += "render/"
                body["voice_id"] = self.voice_id
        else:
            if self.voice_prompt is not None:
                url += "/from-prompt/"
                body["prompt"] = self.voice_prompt
            else:
                body["voice_id"] = self.voice_id
        return url, headers, body
