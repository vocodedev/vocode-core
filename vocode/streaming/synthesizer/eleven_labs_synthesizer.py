import io
import logging
import os
from typing import Optional, List

import aiohttp

from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import (
    ElevenLabsSynthesizerConfig,
    SynthesizerType,
)
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer, FillerAudio, FILLER_AUDIO_PATH,
)
from vocode.streaming.utils import convert_wav
from vocode.streaming.utils.mp3_helper import decode_mp3

ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVEN_LABS_BASE_URL = "https://api.elevenlabs.io/v1/"


class ElevenLabsSynthesizer(BaseSynthesizer[ElevenLabsSynthesizerConfig]):
    def __init__(
            self,
            synthesizer_config: ElevenLabsSynthesizerConfig,
            logger: Optional[logging.Logger] = None,
            aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(synthesizer_config, aiohttp_session)

        import elevenlabs

        self.elevenlabs = elevenlabs

        self.api_key = synthesizer_config.api_key or getenv("ELEVEN_LABS_API_KEY")
        self.voice_id = synthesizer_config.voice_id or ADAM_VOICE_ID
        self.stability = synthesizer_config.stability
        self.similarity_boost = synthesizer_config.similarity_boost
        self.model_id = synthesizer_config.model_id
        self.optimize_streaming_latency = synthesizer_config.optimize_streaming_latency
        self.words_per_minute = 150
        self.experimental_streaming = synthesizer_config.experimental_streaming

    async def create_speech(
            self,
            message: BaseMessage,
            chunk_size: int,
            bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        voice = self.elevenlabs.Voice(voice_id=self.voice_id)
        if self.stability is not None and self.similarity_boost is not None:
            voice.settings = self.elevenlabs.VoiceSettings(
                stability=self.stability, similarity_boost=self.similarity_boost
            )
        url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{self.voice_id}"

        if self.experimental_streaming:
            url += "/stream"

        if self.optimize_streaming_latency:
            url += f"?optimize_streaming_latency={self.optimize_streaming_latency}"
        headers = {"xi-api-key": self.api_key}
        body = {
            "text": message.text,
            "voice_settings": voice.settings.dict() if voice.settings else None,
        }
        if self.model_id:
            body["model_id"] = self.model_id

        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.ELEVEN_LABS.value.split('_', 1)[-1]}.create_total",
        )

        session = self.aiohttp_session

        response = await session.request(
            "POST",
            url,
            json=body,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        )
        if not response.ok:
            raise Exception(f"ElevenLabs API returned {response.status} status code")
        if self.experimental_streaming:
            return SynthesisResult(
                self.experimental_mp3_streaming_output_generator(
                    response, chunk_size, create_speech_span
                ),  # should be wav
                lambda seconds: self.get_message_cutoff_from_voice_speed(
                    message, seconds, self.words_per_minute
                ),
            )
        else:
            audio_data = await response.read()
            create_speech_span.end()
            convert_span = tracer.start_span(
                f"synthesizer.{SynthesizerType.ELEVEN_LABS.value.split('_', 1)[-1]}.convert",
            )
            output_bytes_io = decode_mp3(audio_data)

            result = self.create_synthesis_result_from_wav(
                file=output_bytes_io,
                message=message,
                chunk_size=chunk_size,
            )
            convert_span.end()

            return result

    async def get_phrase_filler_audios(self) -> List[FillerAudio]:
        # FIXME currently it is stored on github but later replace with
        # blob storage & env path to downloaded files.
        filler_phrase_audios = []
        audio_files = os.listdir(FILLER_AUDIO_PATH)
        for audio_file in audio_files:
            wav = open(FILLER_AUDIO_PATH + "/" + audio_file, "rb").read()
            filler_phrase = BaseMessage(text=audio_file.split(".")[0])
            audio_data = convert_wav(
                io.BytesIO(wav),
                output_sample_rate=self.synthesizer_config.sampling_rate,
                output_encoding=self.synthesizer_config.audio_encoding,
            )
            offset_ms = 20
            offset = self.synthesizer_config.sampling_rate * offset_ms // 1000
            audio_data = audio_data[offset:]

            filler_phrase_audios.append(
                FillerAudio(
                    filler_phrase,
                    audio_data=audio_data,
                    synthesizer_config=self.synthesizer_config,
                    is_interruptible=True,
                    seconds_per_chunk=2,
                )
            )

        return filler_phrase_audios
