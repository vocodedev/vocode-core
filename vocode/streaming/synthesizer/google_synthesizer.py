import io
import logging
import os
import wave
from typing import Any, Optional

from google.cloud import texttospeech_v1beta1 as tts
from vocode import getenv

from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    encode_as_wav,
)
from vocode.streaming.models.synthesizer import GoogleSynthesizerConfig
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.utils import convert_wav


class GoogleSynthesizer(BaseSynthesizer):
    OFFSET_SECONDS = 0.5

    def __init__(
        self,
        synthesizer_config: GoogleSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(synthesizer_config)
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
            language_code=synthesizer_config.language_code,
            name=synthesizer_config.voice_name,
        )

        # Select the type of audio file you want returned
        self.audio_config = tts.AudioConfig(
            audio_encoding=tts.AudioEncoding.LINEAR16,
            sample_rate_hertz=24000,
            speaking_rate=synthesizer_config.speaking_rate,
            pitch=synthesizer_config.pitch,
            effects_profile_id=["telephony-class-application"],
        )

    def synthesize(self, message: str) -> tts.SynthesizeSpeechResponse:
        synthesis_input = tts.SynthesisInput(text=message)

        # Perform the text-to-speech request on the text input with the selected
        # voice parameters and audio file type
        return self.client.synthesize_speech(
            request=tts.SynthesizeSpeechRequest(
                input=synthesis_input,
                voice=self.voice,
                audio_config=self.audio_config,
                enable_time_pointing=[
                    tts.SynthesizeSpeechRequest.TimepointType.SSML_MARK
                ],
            )
        )

    def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        response = self.synthesize(message.text)
        output_sample_rate = response.audio_config.sample_rate_hertz

        real_offset = int(GoogleSynthesizer.OFFSET_SECONDS * output_sample_rate)

        output_bytes_io = io.BytesIO()
        in_memory_wav = wave.open(output_bytes_io, "wb")
        in_memory_wav.setnchannels(1)
        in_memory_wav.setsampwidth(2)
        in_memory_wav.setframerate(output_sample_rate)
        in_memory_wav.writeframes(response.audio_content[real_offset:-real_offset])
        output_bytes_io.seek(0)

        return self.create_synthesis_result_from_wav(
            file=output_bytes_io,
            message=message,
            chunk_size=chunk_size,
        )
