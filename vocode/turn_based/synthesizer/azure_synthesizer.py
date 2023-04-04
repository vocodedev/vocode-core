from typing import Optional
import azure.cognitiveservices.speech as speechsdk
from pydub import AudioSegment
from regex import D
from vocode import getenv

from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer

DEFAULT_SAMPLING_RATE = 22050


class AzureSynthesizer(BaseSynthesizer):
    def __init__(
        self,
        sampling_rate: int = DEFAULT_SAMPLING_RATE,
        api_key: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.sampling_rate = sampling_rate
        speech_config = speechsdk.SpeechConfig(
            subscription=getenv("AZURE_SPEECH_KEY", api_key),
            region=getenv("AZURE_SPEECH_REGION", region),
        )
        if self.sampling_rate == 44100:
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Raw44100Hz16BitMonoPcm
            )
        if self.sampling_rate == 48000:
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Raw48Khz16BitMonoPcm
            )
        if self.sampling_rate == 24000:
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm
            )
        if self.sampling_rate == 22050:
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Raw22050Hz16BitMonoPcm
            )
        elif self.sampling_rate == 16000:
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm
            )
        elif self.sampling_rate == 8000:
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm
            )

        self.synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=None
        )

    def synthesize(self, text) -> AudioSegment:
        result = self.synthesizer.speak_text(text)
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return AudioSegment(
                result.audio_data,
                sample_width=2,
                frame_rate=self.sampling_rate,
                channels=1,
            )
        else:
            raise Exception("Could not synthesize audio")
