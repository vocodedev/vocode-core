import io
import logging
from typing import Any, AsyncGenerator, Optional
import time
import aiohttp
from pydub import AudioSegment

from vocode import getenv
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
)
from vocode.streaming.models.synthesizer import (
    ElevenLabsSynthesizerConfig,
    SynthesizerType,
)
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage

from opentelemetry.context.context import Context


ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVEN_LABS_BASE_URL = "https://api.elevenlabs.io/v1/"


class ElevenLabsSynthesizer(BaseSynthesizer[ElevenLabsSynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: ElevenLabsSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(synthesizer_config)

        import elevenlabs

        self.elevenlabs = elevenlabs

        self.api_key = synthesizer_config.api_key or getenv("ELEVEN_LABS_API_KEY")
        self.voice_id = synthesizer_config.voice_id or ADAM_VOICE_ID
        self.stability = synthesizer_config.stability
        self.similarity_boost = synthesizer_config.similarity_boost
        self.model_id = synthesizer_config.model_id
        self.optimize_streaming_latency = synthesizer_config.optimize_streaming_latency
        self.words_per_minute = 150

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

        session = aiohttp.ClientSession()

        response = await session.request(
                "POST",
                url,
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            )
        
        if not response.ok:
            raise Exception(
                f"ElevenLabs API returned {response.status} status code"
            )
        
        async def output_generator(response, session) -> AsyncGenerator[SynthesisResult.ChunkResult, None]:
            buffer = bytearray()
            stream_reader = response.content
            async for chunk in stream_reader.iter_any():
                start_time = time.time()
                audio_segment: AudioSegment = AudioSegment.from_mp3(
                    io.BytesIO(chunk)  # type: ignore
                )
                audio_segment.set_frame_rate(44100)
                output_bytes_io = io.BytesIO()
                audio_segment.export("test.wav", format="wav")  # type: ignore
                print(f"Time to convert: {time.time() - start_time}")

                buffer.extend(output_bytes_io.getvalue())

                at_eof = stream_reader.at_eof()

                if len(buffer) >= chunk_size or at_eof:
                    if at_eof:
                        await session.close()
                    yield SynthesisResult.ChunkResult(buffer, at_eof)
                    buffer.clear()


        create_speech_span.end()

        return SynthesisResult(
            output_generator(response, session), # should be wav
            lambda _: "" # useless for now
        )

    async def old_create_speech(
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
                create_speech_span.end()
                convert_span = tracer.start_span(
                    f"synthesizer.{SynthesizerType.ELEVEN_LABS.value.split('_', 1)[-1]}.convert",
                )
                audio_segment: AudioSegment = AudioSegment.from_mp3(
                    io.BytesIO(audio_data)  # type: ignore
                )

                output_bytes_io = io.BytesIO()

                audio_segment.export(output_bytes_io, format="wav")  # type: ignore

                result = self.create_synthesis_result_from_wav(
                    file=output_bytes_io,
                    message=message,
                    chunk_size=chunk_size,
                )
                convert_span.end()

                return result
        # async with aiohttp.ClientSession() as session:
        #     async with session.post(ENDPOINT, headers=headers, data=data, stream=True) as response:
        #         if response.status_code != 200:
        #             raise Exception(f"API request failed with status code {response.status_code}")
        #         if response.content_type != "audio/mpeg":
        #             raise Exception(f"API response is not in mp3 format")
        #         audio_iterator = response.iter_chunks(chunk_size=1024)
        #         output_generator = (AudioSegment.from_file(io.BytesIO(chunk), format="mp3").set_frame_rate(16000).raw_data for chunk in audio_iterator)
        #         return SynthesisResult(output_generator, lambda seconds: 0)