import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, AsyncGenerator, Optional, Tuple, Union, List, Dict
import wave
import aiohttp
from opentelemetry.trace import Span
from pydub import AudioSegment

from vocode import getenv
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
    FILLER_PHRASES,
    FillerAudio,
    encode_as_wav, BACK_TRACKING_PHRASES
)
from vocode.streaming.models.synthesizer import (
    ElevenLabsSynthesizerConfig,
    SynthesizerType,
)
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.utils.mp3_helper import decode_mp3
from vocode.streaming.synthesizer.miniaudio_worker import MiniaudioWorker
import os
import io
from vocode.streaming.utils import convert_wav

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
        self.logger = logger or logging.getLogger(__name__)

    async def experimental_streaming_output_generator(
            self,
            response: aiohttp.ClientResponse,
            chunk_size: int,
            create_speech_span: Optional[Span],
    ) -> AsyncGenerator[SynthesisResult.ChunkResult, None]:
        miniaudio_worker_input_queue: asyncio.Queue[
            Union[bytes, None]
        ] = asyncio.Queue()
        miniaudio_worker_output_queue: asyncio.Queue[
            Tuple[bytes, bool]
        ] = asyncio.Queue()
        miniaudio_worker = MiniaudioWorker(
            self.synthesizer_config,
            chunk_size,
            miniaudio_worker_input_queue,
            miniaudio_worker_output_queue,
        )
        miniaudio_worker.start()
        stream_reader = response.content

        # Create a task to send the mp3 chunks to the MiniaudioWorker's input queue in a separate loop
        async def send_chunks():
            async for chunk in stream_reader.iter_any():
                miniaudio_worker.consume_nonblocking(chunk)
            miniaudio_worker.consume_nonblocking(None)  # sentinel

        try:
            asyncio.create_task(send_chunks())

            # Await the output queue of the MiniaudioWorker and yield the wav chunks in another loop
            while True:
                # Get the wav chunk and the flag from the output queue of the MiniaudioWorker
                wav_chunk, is_last = await miniaudio_worker.output_queue.get()
                if self.synthesizer_config.should_encode_as_wav:
                    wav_chunk = encode_as_wav(wav_chunk, self.synthesizer_config)

                yield SynthesisResult.ChunkResult(wav_chunk, is_last)
                # If this is the last chunk, break the loop
                if is_last and create_speech_span is not None:
                    create_speech_span.end()
                    break
        except asyncio.CancelledError:
            pass
        finally:
            miniaudio_worker.terminate()

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
                self.experimental_streaming_output_generator(
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

    async def get_phrase_filler_audios(self) -> Dict[str, List[FillerAudio]]:
        filler_phrase_audios = defaultdict(list)
        for emotion, filler_phrases in FILLER_PHRASES.items():
            for filler_phrase in filler_phrases:
                filler_audio_path = await self.get_audio_data_from_cache_or_download(filler_phrase,
                                                                                     self.base_filler_audio_path)
                filler_phrase_audios[emotion].append(
                    FillerAudio(
                        filler_phrase,
                        audio_data=convert_wav(
                            filler_audio_path,
                            output_sample_rate=self.synthesizer_config.sampling_rate,
                            output_encoding=self.synthesizer_config.audio_encoding,
                        ),
                        synthesizer_config=self.synthesizer_config,
                        is_interruptable=True,
                        seconds_per_chunk=2,
                    )
                )
        return filler_phrase_audios

    async def get_phrase_back_tracking_audios(self) -> List[FillerAudio]:
        filler_phrase_audios = []
        for back_tracking_phrase in BACK_TRACKING_PHRASES:
            filler_audio_path = await self.get_audio_data_from_cache_or_download(back_tracking_phrase)

            filler_phrase_audios.append(

                FillerAudio(
                    back_tracking_phrase,
                    audio_data=convert_wav(
                        filler_audio_path,
                        output_sample_rate=self.synthesizer_config.sampling_rate,
                        output_encoding=self.synthesizer_config.audio_encoding,
                    ),
                    synthesizer_config=self.synthesizer_config,
                    is_interruptable=True,
                    seconds_per_chunk=2,
                )
            )
        return filler_phrase_audios

    async def get_audio_data_from_cache_or_download(self, phrase: BaseMessage, base_path: str) -> str:
        cache_key = "-".join(
            (
                str(phrase.text),
                str(self.synthesizer_config.type),
                str(self.synthesizer_config.audio_encoding),
                str(self.synthesizer_config.sampling_rate),
                str(self.voice_id),
                str(self.synthesizer_config.similarity_boost),
                str(self.synthesizer_config.stability),
                str(self.model_id),
            )
        )
        filler_audio_path = os.path.join(base_path, f"{cache_key}.wav")
        if not os.path.exists(filler_audio_path):
            self.logger.debug(f"Generating filler audio for {phrase.text}")
            audio_data = await self.download_filler_audio_data(phrase)

            audio_segment: AudioSegment = AudioSegment.from_mp3(
                io.BytesIO(audio_data)  # type: ignore
            )
            audio_segment.export(filler_audio_path, format="wav")
        return filler_audio_path

    async def download_filler_audio_data(self, back_tracking_phrase):
        voice = self.elevenlabs.Voice(voice_id=self.voice_id)
        if self.stability is not None and self.similarity_boost is not None:
            voice.settings = self.elevenlabs.VoiceSettings(
                stability=self.stability, similarity_boost=self.similarity_boost
            )
        url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{self.voice_id}"
        body = {}
        headers = {}
        if self.optimize_streaming_latency:
            url += f"?optimize_streaming_latency={self.optimize_streaming_latency}"
            headers = {"xi-api-key": self.api_key}
            body = {
                "text": back_tracking_phrase.text,
                "voice_settings": voice.settings.dict() if voice.settings else None,
            }
        if self.model_id:
            body["model_id"] = self.model_id
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
        return audio_data

    @staticmethod
    def save_as_wav(data, filename, sample_rate=44100, sample_width=1, channels=1):
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(data)
