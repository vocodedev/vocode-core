import io

import boto3
from pydub import AudioSegment

from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer

DEFAULT_SAMPLING_RATE = 16000
DEFAULT_LANGUAGE_CODE = "en-US"
DEFAULT_VOICE_ID = "Matthew"


class PollySynthesizer(BaseSynthesizer):
    def __init__(
        self,
        sampling_rate: int = DEFAULT_SAMPLING_RATE,
        language_code: str = DEFAULT_LANGUAGE_CODE,
        voice_id: str = DEFAULT_VOICE_ID,
    ):
        client = boto3.client("polly")

        # AWS Polly supports sampling rate of 8k and 16k for pcm output
        if sampling_rate not in [8000, 16000]:
            raise Exception(
                "Sampling rate not supported by AWS Polly",
                sampling_rate,
            )

        self.sampling_rate = sampling_rate
        self.client = client
        self.language_code = language_code
        self.voice_id = voice_id

    def synthesize(self, message: str) -> AudioSegment:
        response = self.client.synthesize_speech(
            Text=message,
            LanguageCode=self.language_code,
            TextType="text",
            OutputFormat="pcm",
            VoiceId=self.voice_id,
        )

        return AudioSegment(
            response.get("AudioStream").read(),
            sample_width=2,
            frame_rate=self.sampling_rate,
            channels=1,
        )
