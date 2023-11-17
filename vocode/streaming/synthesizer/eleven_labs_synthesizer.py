import asyncio
import hashlib
import io
import logging
import os
import wave
from typing import Optional, List, AsyncGenerator, Union, Tuple, Dict, Callable

import aiohttp
from opentelemetry.trace import Span

from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.agent import FillerAudioConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import (
    ElevenLabsSynthesizerConfig,
    SynthesizerType,
)
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer, FillerAudio, FILLER_AUDIO_PATH, encode_as_wav,
)
from vocode.streaming.synthesizer.miniaudio_worker import MiniaudioWorker
from vocode.streaming.utils.mp3_helper import decode_mp3

ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVEN_LABS_BASE_URL = "https://api.elevenlabs.io/v1/"


class ElevenLabsSynthesizer(BaseSynthesizer[ElevenLabsSynthesizerConfig]):
    def __init__(
            self,
            synthesizer_config: ElevenLabsSynthesizerConfig,
            logger: Optional[logging.Logger] = None,
            aiohttp_session: Optional[aiohttp.ClientSession] = None,
            filler_picker: Optional[Callable] = None,
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
        self.fillers_cache = None
        self.filler_picker = filler_picker

    @property
    def cache_path(self):
        return os.path.join(FILLER_AUDIO_PATH, "elevenlabs", self.model_id, self.voice_id)

    @staticmethod
    def hash_message(message_text: str) -> str:
        hash_object = hashlib.sha1(message_text.encode())
        hashed_text = hash_object.hexdigest()
        return hashed_text

    def pick_filler(self, bot_message: BaseMessage, user_message: BaseMessage) -> Optional[FillerAudio]:
        if self.filler_picker is not None:
            return self.get_cached_audio(self.filler_picker(bot_message.text, user_message.text))
        return None

    def get_cached_audio(self, message_text: str) -> Optional[bytes]:
        file_path = os.path.join(self.cache_path, f"{self.hash_message(message_text)}.wav")
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                return f.read()
        return None

    async def save_audio(self, audio_data: bytes, message_text: str):
        file_path = os.path.join(self.cache_path, f"{self.hash_message(message_text)}.wav")
        # Assuming the sample rate and other parameters are known
        sample_rate = self.synthesizer_config.sampling_rate
        num_channels = 1  # Mono
        sample_width = 2  # Number of bytes per sample (2 for 16-bit audio)

        with wave.open(file_path, 'wb') as wav_file:
            wav_file.setnchannels(num_channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)

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
                accumulated_audio_chunks.append(wav_chunk)
                yield SynthesisResult.ChunkResult(wav_chunk, is_last)
                # If this is the last chunk, break the loop
                if is_last and create_speech_span is not None:
                    self.logger.info(f"Saving audio for {message.text}")
                    complete_audio_data = b''.join(accumulated_audio_chunks)
                    await self.save_audio(complete_audio_data, message.text)
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
                stability=self.stability, similarity_boost=self.similarity_boost
            )
        url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{self.voice_id}"

        if self.experimental_streaming and not ignore_streaming:  # used for fillers prerecording, not for main flow.
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

    async def __save_filler(self, message: str):
        message = BaseMessage(text=message)
        response = await self.__send_request(message, ignore_streaming=True)
        audio_data = await response.read()
        output_bytes_io = decode_mp3(audio_data)
        audio_bytes = output_bytes_io.read()
        await self.save_audio(audio_bytes, message.text)

    async def create_speech(
            self,
            message: BaseMessage,
            chunk_size: int,
            bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:

        cached_audio = self.get_cached_audio(message.text)
        if cached_audio is not None:
            self.logger.info(f"Using cached audio for message: {message.text}")
            return self.create_synthesis_result_from_wav(
                file=io.BytesIO(cached_audio),
                message=message,
                chunk_size=chunk_size
            )

        response = await self.__send_request()
        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.ELEVEN_LABS.value.split('_', 1)[-1]}.create_total",
        )
        if self.experimental_streaming:
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
        # FIXME probably remove it anyway.
        # blob storage & env path to downloaded files.
        filler_phrase_audios = []
        elevenlabs_fillers = os.path.join(FILLER_AUDIO_PATH, "elevenlabs", self.model_id, self.voice_id)
        audio_files = os.listdir(elevenlabs_fillers)
        # for audio_file in audio_files:
        #     wav = open(elevenlabs_fillers + "/" + audio_file, "rb").read()
        #     filler_phrase = BaseMessage(text=audio_file.split(".")[0])
        #     audio_data = convert_wav(
        #         io.BytesIO(wav),
        #         output_sample_rate=self.synthesizer_config.sampling_rate,
        #         output_encoding=self.synthesizer_config.audio_encoding,
        #     )
        #     offset_ms = 20
        #     offset = self.synthesizer_config.sampling_rate * offset_ms // 1000
        #     audio_data = audio_data[offset:]
        #
        #     filler_phrase_audios.append(
        #         FillerAudio(
        #             filler_phrase,
        #             audio_data=audio_data,
        #             synthesizer_config=self.synthesizer_config,
        #             is_interruptible=False,  # FIXME: consider making this configurable.
        #             seconds_per_chunk=2,
        #         )
        #     )

        return filler_phrase_audios

    async def validate_fillers(self, fillers: Dict[str, List[str]]):
        for filler_list in fillers.values():
            for filler_text in filler_list:
                cached_audio = self.get_cached_audio(filler_text)
                if cached_audio is None:
                    self.logger.info(f"Creating audio for missing filler: {filler_text}")
                    await self.__save_filler(filler_text)
