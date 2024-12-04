from enum import Enum

import speech_recognition as sr
from pydub import AudioSegment

from vocode import getenv
from vocode.turn_based.transcriber.base_transcriber import BaseTranscriber


class SpeechRecognitionAPI(Enum):
    SPHINX = "sphinx"
    GOOGLE = "google"
    GOOGLE_CLOUD = "google_cloud"
    WIT = "wit"
    BING = "bing"
    AZURE = "azure"
    HOUNDIFY = "houndify"
    IBM = "ibm"


class SpeechRecognitionTranscriber(BaseTranscriber):
    def __init__(self, api: SpeechRecognitionAPI = SpeechRecognitionAPI.GOOGLE):
        self.api = api

    def transcribe(self, audio_segment: AudioSegment) -> str:
        audio_data = audio_segment.raw_data
        audio = sr.AudioData(
            audio_data,
            sample_rate=audio_segment.frame_rate,
            sample_width=audio_segment.sample_width,
        )

        r = sr.Recognizer()

        try:
            if self.api == SpeechRecognitionAPI.GOOGLE:
                api_key = getenv("GOOGLE_SPEECH_RECOGNITION_API_KEY")
                if not api_key:
                    text = r.recognize_google(audio)
                else:
                    text = r.recognize_google(audio, key=api_key)

            elif self.api == SpeechRecognitionAPI.SPHINX:
                # do note that sphinx requires PocketSphinx to be installed
                text = r.recognize_sphinx(audio)

            elif self.api == SpeechRecognitionAPI.GOOGLE_CLOUD:
                credentials_json = getenv("GOOGLE_CLOUD_SPEECH_CREDENTIALS")
                if not credentials_json:
                    raise ValueError("Google Cloud Speech credentials not provided")
                text = r.recognize_google_cloud(audio, credentials_json=credentials_json)

            elif self.api == SpeechRecognitionAPI.WIT:
                api_key = getenv("WIT_AI_API_KEY")
                if not api_key:
                    raise ValueError("Wit.ai API key not provided")
                text = r.recognize_wit(audio, key=api_key)

            elif self.api == SpeechRecognitionAPI.BING:
                api_key = getenv("BING_API_KEY")
                if not api_key:
                    raise ValueError("Bing API key not provided")
                text = r.recognize_bing(audio, key=api_key)

            elif self.api == SpeechRecognitionAPI.AZURE:
                api_key = getenv("AZURE_SPEECH_KEY")
                region = getenv("AZURE_SPEECH_REGION")
                if not api_key:
                    raise ValueError("Azure Speech API key not provided")
                if not region:
                    raise ValueError("Azure Speech region not provided")
                text = r.recognize_azure(audio, key=api_key, location=region)[0]

            elif self.api == SpeechRecognitionAPI.HOUNDIFY:
                client_id = getenv("HOUNDIFY_CLIENT_ID")
                client_key = getenv("HOUNDIFY_CLIENT_KEY")
                if not client_id or not client_key:
                    raise ValueError("Houndify client ID or key not provided")
                text = r.recognize_houndify(audio, client_id=client_id, client_key=client_key)

            elif self.api == SpeechRecognitionAPI.IBM:
                username = getenv("IBM_USERNAME")
                password = getenv("IBM_PASSWORD")
                if not username or not password:
                    raise ValueError("IBM Speech to Text username or password not provided")
                text = r.recognize_ibm(audio, username=username, password=password)

            else:
                raise ValueError(f"Unsupported API: {self.api}")
        except sr.UnknownValueError:
            raise sr.UnknownValueError("Speech Recognition could not understand audio")
        except sr.RequestError as e:
            raise sr.RequestError(f"Could not request results from Speech Recognition service.")

        return text
