from pydub import AudioSegment
import io
import os
from dotenv import load_dotenv
import openai

from vocode.turn_based.transcriber.base_transcriber import BaseTranscriber

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")


class WhisperTranscriber(BaseTranscriber):
    def transcribe(self, audio_segment: AudioSegment) -> str:
        in_memory_wav = io.BytesIO()
        audio_segment.export(in_memory_wav, format="wav")
        in_memory_wav.seek(0)
        in_memory_wav.name = "whisper.wav"
        transcript = openai.Audio.transcribe("whisper-1", in_memory_wav)
        return transcript.text
