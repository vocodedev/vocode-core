from typing import Optional
from pydub import AudioSegment
import io
import openai
import os
from vocode import getenv

from vocode.turn_based.transcriber.base_transcriber import BaseTranscriber


class WhisperTranscriber(BaseTranscriber):
    def __init__(self, api_key: Optional[str] = None):
        openai.api_key = getenv("OPENAI_API_KEY", api_key)
        if not openai.api_key:
            raise ValueError("OpenAI API key not provided")

        if openai.api_type and "azure" in openai.api_type:
            self.client = openai.AzureOpenAI(
                azure_endpoint = os.getenv("AZURE_OPENAI_API_BASE"),
                api_key = os.getenv("AZURE_OPENAI_API_KEY"),
                api_version = "2023-05-15"
            )
        else:
            self.client = openai.OpenAI(
                api_key=os.getenv("OPENAI_API_KEY")
            )

    def transcribe(self, audio_segment: AudioSegment) -> str:
        in_memory_wav = io.BytesIO()
        audio_segment.export(in_memory_wav, format="wav")  # type: ignore
        in_memory_wav.seek(0)
        in_memory_wav.name = "whisper.wav"

        transcript = self.client.audio.transcriptions.create(
            file=in_memory_wav,
            model="whisper-1",
        )
        return transcript.text
