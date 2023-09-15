import asyncio
import logging
import os
import time
from typing import Any, AsyncGenerator, Optional, Tuple, Union, List
import io
import wave
import aiohttp
from opentelemetry.trace import Span
from pydub import AudioSegment

from vocode import getenv
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    encode_as_wav,
    tracer, FillerAudio, FILLER_AUDIO_PATH,
)
from vocode.streaming.models.synthesizer import (
    ElevenLabsSynthesizerConfig,
    SynthesizerType,
)
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.utils import convert_wav
from vocode.streaming.utils.mp3_helper import decode_mp3
from vocode.streaming.synthesizer.miniaudio_worker import MiniaudioWorker

ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVEN_LABS_BASE_URL = "https://api.elevenlabs.io/v1/"

FILLER_PHRASES = ["Dobře...", "Jo.", "Chápu.", "Jasně"]


async def create_wav(
        message: BaseMessage,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        stability: Optional[float] = None,
        similarity_boost: Optional[float] = None,
        api_key: Optional[str] = None,
        optimize_streaming_latency: Optional[int] = None,

) -> io.BytesIO:
    """
    TODO Mostly copied from pull request. If merged, replace this. https://github.com/vocodedev/vocode-python/pull/215/files
    """

    import elevenlabs
    voice = elevenlabs.Voice(voice_id=voice_id)
    if stability is not None and similarity_boost is not None:
        voice.settings = elevenlabs.VoiceSettings(
            stability=stability, similarity_boost=similarity_boost
        )
    url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{voice_id}"
    headers = {"xi-api-key": api_key}
    body = {
        "text": message.text,
        "voice_settings": voice.settings.dict() if voice.settings else None,
        "model_id":model_id,
    }
    if optimize_streaming_latency:
        body[
            "optimize_streaming_latency"
        ] = optimize_streaming_latency

    async with aiohttp.ClientSession() as session:
        async with session.request(
                "POST",
                url,
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            if not response.ok:
                raise Exception(
                    f"ElevenLabs API returned {response.status} status code"
                )
            audio_data = await response.read()
            audio_segment: AudioSegment = AudioSegment.from_mp3(
                io.BytesIO(audio_data)  # type: ignore
            )

            output_bytes_io = io.BytesIO()

            audio_segment.export(output_bytes_io, format="wav")  # type: ignore

            return output_bytes_io


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
        filler_phrase_audios = []
        filler_phrases = [BaseMessage(text=phrase) for phrase in FILLER_PHRASES]
        for filler_phrase in filler_phrases:
            cache_key = "-".join(
                (
                    str(filler_phrase),
                    str(self.synthesizer_config.type),
                    str(self.synthesizer_config.audio_encoding),
                    str(self.synthesizer_config.sampling_rate),
                    str(self.voice_id),
                    str(self.model_id),
                    str(self.words_per_minute),
                )
            )
            filler_audio_path = os.path.join(FILLER_AUDIO_PATH, f"{cache_key}.wav")
            if os.path.exists(filler_audio_path):
                wav = open(filler_audio_path, "rb").read()
            else:
                # self.logger.debug(f"Generating filler audio for {filler_phrase.text}")
                wav = (await create_wav(filler_phrase,
                                        voice_id=self.voice_id,
                                        model_id=self.model_id,
                                        stability=self.stability,
                                        similarity_boost=self.similarity_boost,
                                        api_key=self.api_key,
                                        optimize_streaming_latency=self.synthesizer_config.optimize_streaming_latency,
                                        )).read()

                with open(filler_audio_path, "wb") as f:
                    f.write(wav)
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
