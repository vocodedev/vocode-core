import asyncio
import audioop
import hashlib
import logging
import os
from io import BytesIO
from typing import Optional, List, AsyncGenerator, Union, Tuple, Any

import aiohttp
from opentelemetry.trace import Span
from pydub import AudioSegment

from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.agent import FillerAudioConfig
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import (
    ElevenLabsSynthesizerConfig,
    SynthesizerType, ELEVEN_LABS_MULAW_8000,
)
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer, FillerAudio, FILLER_AUDIO_PATH, encode_as_wav,
)
from vocode.streaming.synthesizer.miniaudio_worker import MiniaudioWorker
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
            filler_picker: Optional[Any] = None,
            ignore_cache=False
            # FIXME: consider unifying it. For now it has Any to prevent circular imports.
    ):
        super().__init__(synthesizer_config, aiohttp_session)

        import elevenlabs

        self.elevenlabs = elevenlabs

        self.api_key = synthesizer_config.api_key or getenv("ELEVEN_LABS_API_KEY")
        self.voice_id = synthesizer_config.voice_id or ADAM_VOICE_ID
        self.stability = synthesizer_config.stability
        self.similarity_boost = synthesizer_config.similarity_boost
        self.use_speaker_boost = synthesizer_config.use_speaker_boost
        self.model_id = synthesizer_config.model_id
        self.optimize_streaming_latency = synthesizer_config.optimize_streaming_latency
        self.words_per_minute = 150
        self.experimental_streaming = synthesizer_config.experimental_streaming
        self.output_format = synthesizer_config.output_format

        self.logger = logger or logging.getLogger(__name__)
        self.fillers_cache = None
        self.filler_picker = filler_picker
        self.ignore_cache = ignore_cache

    @property
    def cache_path(self):
        filler_path = FILLER_AUDIO_PATH if os.getenv("FILLER_AUDIO_PATH") is None else os.getenv("FILLER_AUDIO_PATH")
        return os.path.join(filler_path, "elevenlabs", self.model_id, self.voice_id, self.output_format)

    @staticmethod
    def hash_message(message_text: str) -> str:
        hash_object = hashlib.sha1(message_text.encode())
        hashed_text = hash_object.hexdigest()
        return hashed_text

    def speed_up_audio(input_stream, speed_factor):
        # USAGE: audio_data = self.speed_up_audio(audio_data, 1.20)
        # Load the audio file from the byte stream
        audio = AudioSegment.from_file(input_stream)

        # Speed up the audio
        sped_up_audio = audio.speedup(playback_speed=speed_factor)

        # Create a byte stream for the output
        output_stream = BytesIO()
        sped_up_audio.export(output_stream, format="mp3")

        # Reset stream position to the beginning
        output_stream.seek(0)

        return output_stream

    async def pick_filler(self, bot_message: str, user_message: str) -> Optional[FillerAudio]:
        if self.filler_picker is not None:
            self.logger.info(f'Using filler picker for "{bot_message}" and "{user_message}"')
            pick = self.filler_picker.predict_filler_phrase(bot_message, user_message)
            self.logger.info("Picking filler")
            if pick is not None:
                self.logger.info(f"Filler picked: {pick}")
                audio_data = self.get_cached_audio(pick)
                if audio_data is None:
                    # Create & cache missing filler.
                    await self.save_filler_to_cache(pick)
                    audio_data = self.get_cached_audio("yes yes")
                if self.output_format != ELEVEN_LABS_MULAW_8000:
                    # TODO Mulaw could also use resampling and encoding, but it is not used now.
                    # Below also converts to linear, which is not desirable for Mulaw
                    audio_data = convert_wav(
                        audio_data,
                        output_sample_rate=self.synthesizer_config.sampling_rate,
                        output_encoding=self.synthesizer_config.audio_encoding,
                    )

                return FillerAudio(
                    BaseMessage(text=pick),
                    audio_data=audio_data,
                    synthesizer_config=self.synthesizer_config,
                    is_interruptible=True
                )
            self.logger.warning(f"Filler picker returned None for {bot_message} and {user_message}")
        return None

    def read_audio_from_cache(self, message_text: str):
        file_extension = self.synthesizer_config.output_format_to_cache_file_extension()
        file_path = os.path.join(self.cache_path, f"{self.hash_message(message_text)}.{file_extension}")
        if os.path.exists(file_path):
            return open(file_path, "rb").read()
        return None

    def get_cached_audio(self, message_text: str) -> Optional[bytes]:
        audio_data = self.read_audio_from_cache(message_text)
        if audio_data is not None:
            if self.output_format == ELEVEN_LABS_MULAW_8000:
                if self.synthesizer_config.audio_encoding == AudioEncoding.LINEAR16:
                    audio_data = audioop.ulaw2lin(audio_data, 2)

                return audio_data

            else:
                output_bytes_io = decode_mp3(audio_data)
                return output_bytes_io.getvalue()

        return None

    async def save_audio_to_cache(self, audio_data: bytes, message_text: str):
        if self.ignore_cache:
            self.logger.info("Ignoring cache")
            return
        os.makedirs(self.cache_path, exist_ok=True)
        file_extension = self.synthesizer_config.output_format_to_cache_file_extension()
        file_path = os.path.join(self.cache_path, f"{self.hash_message(message_text)}.{file_extension}")

        with open(file_path, 'wb') as file:
            file.write(audio_data)

    def set_fillers_cache(self):
        self.fillers_cache = {}
        self.logger.info("Setting filler cache")
        self.logger.info(f"{len(self.filler_audios)} filler audios are available")
        for filler_audio in self.filler_audios:
            self.fillers_cache[filler_audio.message.text] = filler_audio

    async def set_filler_audios(self, filler_audio_config: FillerAudioConfig):
        if filler_audio_config.use_phrases:
            self.filler_audios = await self.get_phrase_filler_audios()
            self.set_fillers_cache()

    async def get_filler(self, hash_val: str) -> FillerAudio:
        if self.fillers_cache is None:
            self.set_fillers_cache()
        return self.fillers_cache.get(hash_val, None)  # FIXME: what should we do on cache miss?

    def create_synthesis_result_from_bytes(self, audio_data: bytes, message: BaseMessage,
                                           chunk_size: Optional[int] = None) -> SynthesisResult:
        if self.synthesizer_config.output_format_to_cache_file_extension() == 'mulaw':
            if self.synthesizer_config.audio_encoding == AudioEncoding.LINEAR16:
                audio_data = audioop.ulaw2lin(audio_data, 2)

            async def generator():
                # TODO there is no-rechunking
                yield SynthesisResult.ChunkResult(audio_data, True)

            result = SynthesisResult(
                generator(),  # should be wav
                lambda seconds: self.get_message_cutoff_from_voice_speed(
                    message, seconds, self.words_per_minute
                ),
            )

        elif self.synthesizer_config.output_format_to_cache_file_extension() == 'mp3':
            output_bytes_io = decode_mp3(audio_data)
            result = self.create_synthesis_result_from_wav(
                file=output_bytes_io,
                message=message,
                chunk_size=chunk_size,
            )

        else:
            raise Exception(f"Unknown output format: {self.synthesizer_config.output_format_to_cache_file_extension()}")

        return result

    async def experimental_direct_streaming_output_generator(self, response: aiohttp.ClientResponse,
                                                             message: BaseMessage) -> AsyncGenerator[
        SynthesisResult.ChunkResult, None]:
        accumulated_audio_chunks = []
        response: aiohttp.ClientResponse
        stream_reader = response.content
        # Chunked as they come from Elevenlabs
        async for chunk in stream_reader.iter_any():
            accumulated_audio_chunks.append(chunk)
            if self.output_format == ELEVEN_LABS_MULAW_8000 and self.synthesizer_config.audio_encoding == AudioEncoding.LINEAR16:
                chunk = audioop.ulaw2lin(chunk, 2)

            yield SynthesisResult.ChunkResult(chunk, True)

        complete_audio_data = b''.join(accumulated_audio_chunks)
        self.logger.info(f"Saving audio for message: {message.text}")
        await self.save_audio_to_cache(complete_audio_data, message.text)

    async def experimental_mp3_streaming_output_generator(
            self,
            response: aiohttp.ClientResponse,
            chunk_size: int,
            create_speech_span: Optional[Span],
            message: BaseMessage
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

        accumulated_audio_chunks = []

        # Create a task to send the mp3 chunks to the MiniaudioWorker's input queue in a separate loop
        async def send_chunks():
            async for chunk in stream_reader.iter_any():
                accumulated_audio_chunks.append(chunk)
                miniaudio_worker.consume_nonblocking(chunk)
            miniaudio_worker.consume_nonblocking(None)  # sentinel
            complete_audio_data = b''.join(accumulated_audio_chunks)
            self.logger.info(f"Saving audio for message: {message.text}")
            await self.save_audio_to_cache(complete_audio_data, message.text)

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

    async def __send_request(self, message: BaseMessage, ignore_streaming: bool = False):
        voice = self.elevenlabs.Voice(voice_id=self.voice_id)
        if self.stability is not None and self.similarity_boost is not None:
            voice.settings = self.elevenlabs.VoiceSettings(
                stability=self.stability, similarity_boost=self.similarity_boost,
                use_speaker_boost=self.use_speaker_boost
            )
        url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{self.voice_id}"

        if self.experimental_streaming and not ignore_streaming:  # used for fillers prerecording, not for main flow.
            url += "/stream"

        if self.optimize_streaming_latency:
            url += f"?optimize_streaming_latency={self.optimize_streaming_latency}"

        url += f"&output_format={self.output_format}"

        headers = {"xi-api-key": self.api_key}
        body = {
            "text": message.text,
            "voice_settings": voice.settings.dict() if voice.settings else None,
        }
        if self.model_id:
            body["model_id"] = self.model_id

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
        return response

    async def save_filler_to_cache(self, message: str):
        message = BaseMessage(text=message)
        response = await self.__send_request(message, ignore_streaming=True)
        # Storing audio as it arrives to avoid re-coding distortion.
        # Files take up space on disk, but ulaw_8000 is small as mp3 44k.
        audio_data = await response.read()
        await self.save_audio_to_cache(audio_data, message.text)

    async def create_speech(
            self,
            message: BaseMessage,
            chunk_size: int,
            bot_sentiment: Optional[BotSentiment] = None
    ) -> SynthesisResult:
        if not self.ignore_cache:
            cached_audio = self.get_cached_audio(message.text)
            if cached_audio is not None:
                self.logger.info(f"Using cached audio for message: {message.text}")

                async def generator():
                    yield SynthesisResult.ChunkResult(cached_audio, True)

                return SynthesisResult(
                    generator(),  # should be wav
                    lambda seconds: self.get_message_cutoff_from_voice_speed(
                        message, seconds, self.words_per_minute
                    ),
                )

        response = await self.__send_request(message)
        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.ELEVEN_LABS.value.split('_', 1)[-1]}.create_total",
        )
        if self.experimental_streaming:
            if self.output_format == ELEVEN_LABS_MULAW_8000:
                return SynthesisResult(
                    self.experimental_direct_streaming_output_generator(
                        response, message
                    ),  # should be wav
                    lambda seconds: self.get_message_cutoff_from_voice_speed(
                        message, seconds, self.words_per_minute
                    ),
                )
            else:
                # MP3
                return SynthesisResult(
                    self.experimental_mp3_streaming_output_generator(
                        response, chunk_size, create_speech_span, message
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

            result = self.create_synthesis_result_from_bytes(audio_data, message)

            convert_span.end()

            return result

    async def get_phrase_filler_audios(self) -> List[FillerAudio]:
        # Kept for compatibility with the old code.
        filler_phrase_audios = []

        return filler_phrase_audios

    async def validate_fillers(self, flush_cache: bool = False):
        if self.filler_picker is None:
            self.logger.info("No filler picker provided, skipping fillers validation")
            return

        for filler_text in self.filler_picker.all_fillers:
            cached_audio = self.read_audio_from_cache(filler_text)
            if cached_audio is None or flush_cache:
                self.logger.info(f"Creating audio for missing filler: {filler_text}")
                await self.save_filler_to_cache(filler_text)

        # TODO generate other parts of call script to cache from prompt JSON also
