import io
from typing import Optional

import openai
from pydub import AudioSegment

from vocode import getenv
from vocode.turn_based.transcriber.base_transcriber import BaseTranscriber


class WhisperTranscriber(BaseTranscriber):
    def __init__(self, api_key: Optional[str] = None):
        api_key = getenv("OPENAI_API_KEY", api_key)
        if not api_key:
            raise ValueError("OpenAI API key not provided")
        self.client = openai.OpenAI(api_key=api_key)

    def transcribe(self, audio_segment: AudioSegment) -> str:
        in_memory_wav = io.BytesIO()
        audio_segment.export(in_memory_wav, format="wav")  # type: ignore
        in_memory_wav.seek(0)
        in_memory_wav.name = "whisper.wav"
        transcript = self.client.audio.transcriptions.create(model="whisper-1", file=in_memory_wav)
        return transcript.text
