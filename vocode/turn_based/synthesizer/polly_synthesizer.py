import io
from pydub import AudioSegment
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer

import boto3

DEFAULT_LANGUAGE_CODE = "en-US"
DEFAULT_VOICE_ID = "Matthew"

class PollySynthesizer(BaseSynthesizer):
    def __init__(
        self,
        language_code: str = DEFAULT_LANGUAGE_CODE,
        voice_id: str = DEFAULT_VOICE_ID,
    ):
        client = boto3.client("polly")

        self.client = client
        self.language_code = language_code
        self.voice_id = voice_id

    def synthesize(self, message: str) -> AudioSegment:
        response = self.client.synthesize_speech(
            Text=message, 
            LanguageCode=self.language_code,
            TextType="text", 
            OutputFormat="mp3",
            VoiceId=self.voice_id, 
        )
        return AudioSegment.from_mp3(io.BytesIO(response.get("AudioStream").read()))
