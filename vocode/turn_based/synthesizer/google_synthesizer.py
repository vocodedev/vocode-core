import io
import os
from typing import Optional
from pydub import AudioSegment
import requests
from vocode import getenv
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer
from google.cloud import texttospeech_v1beta1 as tts


class GoogleSynthesizer(BaseSynthesizer):
    def __init__(self):
        self.tts = tts
        DEFAULT_GOOGLE_LANGUAGE_CODE = "en-US"
        DEFAULT_GOOGLE_VOICE_NAME = "en-US-Neural2-I"
        DEFAULT_GOOGLE_PITCH = 0
        DEFAULT_GOOGLE_SPEAKING_RATE = 1.2

        # Instantiates a client
        credentials_path = getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_path:
            raise Exception(
                "Please set GOOGLE_APPLICATION_CREDENTIALS environment variable"
            )
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        self.client = tts.TextToSpeechClient()

        # Build the voice request, select the language code ("en-US") and the ssml
        # voice gender ("neutral")
        self.voice = tts.VoiceSelectionParams(
            language_code=DEFAULT_GOOGLE_LANGUAGE_CODE,
            name=DEFAULT_GOOGLE_VOICE_NAME,
        )

        # Select the type of audio file you want returned
        self.audio_config = tts.AudioConfig(
            audio_encoding=tts.AudioEncoding.LINEAR16,
            sample_rate_hertz=24000,
            speaking_rate=DEFAULT_GOOGLE_SPEAKING_RATE,
            pitch=DEFAULT_GOOGLE_PITCH,
            effects_profile_id=["telephony-class-application"],
        )

    def synthesize(self, message: str) -> AudioSegment:
        synthesis_input = self.tts.SynthesisInput(text=message)

        response = self.client.synthesize_speech(
            request=self.tts.SynthesizeSpeechRequest(
                input=synthesis_input,
                voice=self.voice,
                audio_config=self.audio_config,
                enable_time_pointing=[
                    self.tts.SynthesizeSpeechRequest.TimepointType.SSML_MARK
                ],
            )
        )

        return AudioSegment.from_wav(io.BytesIO(response.audio_content))