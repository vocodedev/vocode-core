from typing import Optional
from xml.etree import ElementTree

from pydub import AudioSegment
from regex import D

from vocode import getenv
from vocode.turn_based.synthesizer.base_synthesizer import BaseSynthesizer

DEFAULT_SAMPLING_RATE = 22050
DEFAULT_VOICE_NAME = "en-US-AriaNeural"
DEFAULT_PITCH = 0
DEFAULT_RATE = 15

NAMESPACES = {
    "mstts": "https://www.w3.org/2001/mstts",
    "": "https://www.w3.org/2001/10/synthesis",
}

ElementTree.register_namespace("", NAMESPACES[""])
ElementTree.register_namespace("mstts", NAMESPACES["mstts"])


class AzureSynthesizer(BaseSynthesizer):
    def __init__(
        self,
        sampling_rate: int = DEFAULT_SAMPLING_RATE,
        voice_name: str = DEFAULT_VOICE_NAME,
        pitch: int = DEFAULT_PITCH,
        rate: int = DEFAULT_RATE,
        api_key: Optional[str] = None,
        region: Optional[str] = None,
    ):
        import azure.cognitiveservices.speech as speechsdk

        self.speechsdk = speechsdk

        self.sampling_rate = sampling_rate
        speech_config = self.speechsdk.SpeechConfig(
            subscription=getenv("AZURE_SPEECH_KEY", api_key),
            region=getenv("AZURE_SPEECH_REGION", region),
        )
        if self.sampling_rate == 44100:
            speech_config.set_speech_synthesis_output_format(
                self.speechsdk.SpeechSynthesisOutputFormat.Raw44100Hz16BitMonoPcm
            )
        if self.sampling_rate == 48000:
            speech_config.set_speech_synthesis_output_format(
                self.speechsdk.SpeechSynthesisOutputFormat.Raw48Khz16BitMonoPcm
            )
        if self.sampling_rate == 24000:
            speech_config.set_speech_synthesis_output_format(
                self.speechsdk.SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm
            )
        if self.sampling_rate == 22050:
            speech_config.set_speech_synthesis_output_format(
                self.speechsdk.SpeechSynthesisOutputFormat.Raw22050Hz16BitMonoPcm
            )
        elif self.sampling_rate == 16000:
            speech_config.set_speech_synthesis_output_format(
                self.speechsdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm
            )
        elif self.sampling_rate == 8000:
            speech_config.set_speech_synthesis_output_format(
                self.speechsdk.SpeechSynthesisOutputFormat.Raw8Khz16BitMonoPcm
            )

        self.synthesizer = self.speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=None
        )
        self.voice_name = voice_name
        self.pitch = pitch
        self.rate = rate

    def create_ssml(self, message: str) -> str:
        ssml_root = ElementTree.fromstring(
            '<speak version="1.0" xmlns="https://www.w3.org/2001/10/synthesis" xml:lang="en-US"></speak>'
        )
        voice = ElementTree.SubElement(ssml_root, "voice")
        voice.set("name", self.voice_name)
        voice_root = voice
        prosody = ElementTree.SubElement(voice_root, "prosody")
        prosody.set("pitch", f"{self.pitch}%")
        prosody.set("rate", f"{self.rate}%")
        prosody.text = message.strip()
        return ElementTree.tostring(ssml_root, encoding="unicode")

    def synthesize(self, text) -> AudioSegment:
        result = self.synthesizer.speak_ssml(self.create_ssml(text))
        if result.reason == self.speechsdk.ResultReason.SynthesizingAudioCompleted:
            return AudioSegment(
                result.audio_data,
                sample_width=2,
                frame_rate=self.sampling_rate,
                channels=1,
            )
        else:
            raise Exception("Could not synthesize audio")
