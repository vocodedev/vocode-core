import io
from typing import Optional

from google.cloud import texttospeech_v1beta1 as tts  # type: ignore
from pydub import AudioSegment

from vocode import getenv
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer

DEFAULT_LANGUAGE_CODE = "en-US"
DEFAULT_VOICE_NAME = "en-US-Neural2-I"
DEFAULT_PITCH = 0
DEFAULT_SPEAKING_RATE = 1.2
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_AUDIO_ENCODING = tts.AudioEncoding.LINEAR16
DEFAULT_TIME_POINTING = [tts.SynthesizeSpeechRequest.TimepointType.TIMEPOINT_TYPE_UNSPECIFIED]


class GoogleSynthesizer(BaseSynthesizer):
    def __init__(
        self,
        language_code: str = DEFAULT_LANGUAGE_CODE,
        voice_name: str = DEFAULT_VOICE_NAME,
        pitch: int = DEFAULT_PITCH,
        speaking_rate: float = DEFAULT_SPEAKING_RATE,
        sample_rate_hertz: int = DEFAULT_SAMPLE_RATE,
        audio_encoding=DEFAULT_AUDIO_ENCODING,
        effects_profile_id: Optional[str] = None,
        enable_time_pointing: Optional[list] = DEFAULT_TIME_POINTING,
    ):
        import google.auth

        google.auth.default()
        self.client = tts.TextToSpeechClient()

        self.voice = tts.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name,
        )

        self.audio_config = tts.AudioConfig(
            audio_encoding=audio_encoding,
            sample_rate_hertz=sample_rate_hertz,
            speaking_rate=speaking_rate,
            pitch=pitch,
            effects_profile_id=effects_profile_id,
        )

        self.enable_time_pointing = enable_time_pointing

    def synthesize(self, message: str) -> AudioSegment:
        synthesis_input = tts.SynthesisInput(text=message)

        response = self.client.synthesize_speech(
            request=tts.SynthesizeSpeechRequest(
                input=synthesis_input,
                voice=self.voice,
                audio_config=self.audio_config,
                enable_time_pointing=self.enable_time_pointing,
            )
        )

        return AudioSegment.from_wav(io.BytesIO(response.audio_content))  # type: ignore
