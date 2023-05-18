from typing import Optional
from pydub import AudioSegment
import io
import openai
from vocode import getenv

from vocode.turn_based.transcriber.base_transcriber import BaseTranscriber


class WhisperTranscriber(BaseTranscriber):
    def __init__(self, api_key: Optional[str] = None):
        openai.api_key = getenv("OPENAI_API_KEY", api_key)
        if not openai.api_key:
            raise ValueError("OpenAI API key not provided")

    def transcribe(self, audio_segment: AudioSegment) -> str:
        in_memory_wav = io.BytesIO()
        audio_segment.export(in_memory_wav, format="wav")  # type: ignore
        in_memory_wav.seek(0)
        in_memory_wav.name = "whisper.wav"
        transcript = openai.Audio.transcribe("whisper-1", in_memory_wav)
        return transcript.text
