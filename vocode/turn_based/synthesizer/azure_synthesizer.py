import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
from pydub import AudioSegment

from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer

load_dotenv()


class AzureSynthesizer(BaseSynthesizer):
    def __init__(self, sampling_rate: int):
        self.sampling_rate = sampling_rate
        speech_config = speechsdk.SpeechConfig(
            subscription=os.environ.get("AZURE_SPEECH_KEY"),
            region=os.environ.get("AZURE_SPEECH_REGION"),
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
