import io
from typing import Optional

from elevenlabs import Voice, VoiceSettings
from elevenlabs.client import ElevenLabs
from pydub import AudioSegment

from vocode import getenv
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer


class ElevenLabsSynthesizer(BaseSynthesizer):
    def __init__(
        self,
        voice_id: str,
        stability: Optional[float] = None,
        similarity_boost: Optional[float] = None,
        api_key: Optional[str] = None,
    ):

        self.voice_id = voice_id
        self.api_key = getenv("ELEVEN_LABS_API_KEY", api_key)

        self.elevenlabs_client = ElevenLabs(
            api_key=self.api_key,
        )
        self.validate_stability_and_similarity_boost(stability, similarity_boost)
        self.stability = stability
        self.similarity_boost = similarity_boost

    def validate_stability_and_similarity_boost(
        self, stability: Optional[float], similarity_boost: Optional[float]
    ) -> None:
        if (stability is None) != (similarity_boost is None):
            raise ValueError("Both stability and similarity_boost must be set or not set.")

    def synthesize(self, text: str) -> AudioSegment:
        if self.stability is not None and self.similarity_boost is not None:
            voice = Voice(
                voice_id=self.voice_id,
                settings=VoiceSettings(
                    stability=self.stability, similarity_boost=self.similarity_boost
                ),
            )
        else:
            voice = Voice(voice_id=self.voice_id)

        audio = self.elevenlabs_client.generate(text=text, voice=voice)

        return AudioSegment.from_mp3(io.BytesIO(audio))  # type: ignore
