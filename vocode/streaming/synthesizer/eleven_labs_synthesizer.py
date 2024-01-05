import asyncio
import logging
import time
import os
import io
from typing import List, Any, AsyncGenerator, Optional, Tuple, Union, Dict
import wave
import aiohttp
from opentelemetry import trace
from opentelemetry.trace import Span, set_span_in_context
from pydub import AudioSegment
from langchain.docstore.document import Document
import base64
from botocore.client import Config
from vocode import getenv
from vocode.streaming.synthesizer.base_synthesizer import (
    # BaseSynthesizer, # this wont reflect the changes in the base_synthesizer.py when editing
    SynthesisResult,
    FillerAudio,
    encode_as_wav,
    tracer,
)
from vocode.streaming.models.agent import (
    FillerAudioConfig,
    FollowUpAudioConfig,
    BacktrackAudioConfig,
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
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer

from vocode.streaming.utils.aws_s3 import load_from_s3, load_from_s3_async
from vocode.streaming.utils.cache import RedisRenewableTTLCache

ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVEN_LABS_BASE_URL = "https://api.elevenlabs.io/v1/"

SIMILARITY_THRESHOLD = 0.98

s3_config = Config(s3={"use_accelerate_endpoint": True})


class ElevenLabsSynthesizer(BaseSynthesizer[ElevenLabsSynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: ElevenLabsSynthesizerConfig,
        cache: Optional[RedisRenewableTTLCache] = None,
        logger: Optional[logging.Logger] = None,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(
            synthesizer_config,
            cache=cache,
            logger=logger,
            aiohttp_session=aiohttp_session,
        )

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
        self.vector_db = None
        self.bucket_name = None

        if synthesizer_config.index_config:
            from vocode.streaming.vector_db.pinecone import PineconeDB

            self.vector_db = PineconeDB(synthesizer_config.index_config.pinecone_config)
            self.bucket_name = synthesizer_config.index_config.bucket_name

    async def download_filler_audio_data(self, filler_phrase: BaseMessage) -> bytes:
        voice = self.elevenlabs.Voice(voice_id=self.voice_id)
        if self.stability is not None and self.similarity_boost is not None:
            voice.settings = self.elevenlabs.VoiceSettings(
                stability=self.stability, similarity_boost=self.similarity_boost
            )
        url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{self.voice_id}"
        headers = {"xi-api-key": self.api_key}
        body = {
            "text": filler_phrase.text,
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

    async def get_audio_data_from_cache_or_download(
        self, phrase: BaseMessage, base_path: str
    ) -> str:
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
            self.logger.debug(f"Generating cached audio for {phrase.text}")
            audio_data: bytes = await self.download_filler_audio_data(phrase)
            audio_segment: AudioSegment = AudioSegment.from_mp3(
                io.BytesIO(audio_data)  # type: ignore
            )
            audio_segment.export(filler_audio_path, format="wav")
        return filler_audio_path

    async def get_audios_from_messages(
        self,
        phrases: List[BaseMessage],
        base_path: str,
        audio_is_interruptible: bool = True,
    ) -> List[FillerAudio]:
        if not os.path.exists(base_path):
            os.makedirs(base_path)
        audios = []
        for phrase in phrases:
            audio_path = await self.get_audio_data_from_cache_or_download(
                phrase, base_path
            )
            audio_data = convert_wav(
                audio_path,
                output_sample_rate=self.synthesizer_config.sampling_rate,
                output_encoding=self.synthesizer_config.audio_encoding,
            )
            audio = FillerAudio(
                phrase,
                audio_data=audio_data,
                synthesizer_config=self.synthesizer_config,
                is_interruptible=audio_is_interruptible,
                seconds_per_chunk=2,
            )
            audios.append(audio)
        return audios

    async def get_phrase_filler_audios(
        self, filler_audio_config: FillerAudioConfig
    ) -> Dict[str, List[FillerAudio]]:
        
        language = filler_audio_config.language
        filler_dict: Dict[str, List[str]] = filler_audio_config.filler_phrases.get(language)
        filler_phrase_list = self.make_filler_phrase_list(filler_dict)

        filler_phrase_audios = {}
        audios = await self.get_audios_from_messages(
            filler_phrase_list, self.base_filler_audio_path
        )
        for key, phrase_text_list in filler_dict.items():
            filler_phrase_audios[key]: List = []
            for phrase_text in phrase_text_list:
                for audio in audios:
                    if audio.message.text == phrase_text:
                        filler_phrase_audios[key].append(audio)

        return filler_phrase_audios

    def get_result_from_mp3_audio_data(
        self, audio_data: bytes, message: BaseMessage, chunk_size: int
    ) -> SynthesisResult:
        output_bytes_io = decode_mp3(audio_data)
        result = self.create_synthesis_result_from_wav(
            synthesizer_config=self.synthesizer_config,
            file=output_bytes_io,
            message=BaseMessage(text=message.text),
            chunk_size=chunk_size,
        )
        return result

    # @tracer.start_as_current_span(
    #     f"synthesizer.{SynthesizerType.ELEVEN_LABS.value.split('_', 1)[-1]}.index",
    # )
    async def get_result_from_index(self, message: BaseMessage, chunk_size: int):
        self.logger.debug(f'Checking vector_db for "{message.text}"...')
        index_filter = None
        if self.stability is not None and self.similarity_boost is not None:
            index_filter = {
                "stability": self.stability,
                "similarity_boost": self.similarity_boost,
                "voice_id": self.voice_id,
            }

        query_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.ELEVEN_LABS.value.split('_', 1)[-1]}.query"
        )
        result_embeds: List[
            Tuple[Document, float]
        ] = await self.vector_db.similarity_search_with_score(
            query=message.text, filter=index_filter
        )
        query_span.end()

        if result_embeds:
            doc, score = result_embeds[0]  # top result
            if score > SIMILARITY_THRESHOLD:
                object_id = doc.metadata.get("object_key")
                text_message = doc.page_content
                self.logger.debug(
                    f"Found similar synthesized text in vector_db: {text_message}"
                )
                self.logger.debug(f"Original text: {message.text}")
                index_message = BaseMessage(text=text_message)
                try:
                    s3_span = tracer.start_span(
                        f"synthesizer.{SynthesizerType.ELEVEN_LABS.value.split('_', 1)[-1]}.s3"
                    )
                    async with self.aiobotocore_session.create_client(
                        "s3", config=s3_config
                    ) as _s3:
                        audio_data = await load_from_s3_async(
                            bucket_name=self.bucket_name,
                            object_key=object_id,
                            s3_client=_s3,
                        )
                    s3_span.end()
                except Exception as e:
                    self.logger.debug(f"Error loading object from S3: {str(e)}")
                    audio_data = None
                if audio_data is not None:
                    if self.cache:
                        self.logger.debug(f"Adding {text_message} to cache.")
                        cache_key = self.get_cache_key(text_message)
                        self.logger.debug(f"Cache key: {cache_key}")
                        self.cache.set(cache_key, base64.b64encode(audio_data))
                    result = self.get_result_from_mp3_audio_data(
                        audio_data, message, chunk_size
                    )
                    return result, index_message
                else:
                    return None, index_message

        return None, None

    @tracer.start_as_current_span(
        f"synthesizer.{SynthesizerType.ELEVEN_LABS.value.split('_', 1)[-1]}.create_speech",
    )
    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
        return_tuple: Optional[bool] = False,
    ) -> Union[SynthesisResult, Tuple[SynthesisResult, BaseMessage]]:
        # check local cache
        if self.cache:
            self.logger.debug(f"Checking cache for: {message.text}")
            cache_key = self.get_cache_key(message.text)
            self.logger.debug(f"Cache key: {cache_key}")
            audio_encoded = self.cache.get(cache_key)
            if audio_encoded is not None:
                self.logger.debug(
                    f"Retrieving text from synthesizer cache: {message.text}"
                )
                audio_data = base64.b64decode(audio_encoded)
                result = self.get_result_from_mp3_audio_data(
                    audio_data, message, chunk_size
                )
                if return_tuple:
                    return result, message
                else:
                    return result

        # check vector db
        return_with_index_task = None
        if self.vector_db and self.bucket_name:

            async def return_with_index():
                result: SynthesisResult
                index_message: BaseMessage
                result, index_message = await self.get_result_from_index(
                    message, chunk_size
                )
                if result is not None:
                    if return_tuple:
                        return result, index_message
                    else:
                        return result

            return_with_index_task = asyncio.create_task(
                return_with_index(), name="return_with_index"
            )

        return_with_elevenlabs_task = None

        async def return_with_elevenlabs():
            self.logger.debug(f"Synthesizing: {message.text}")
            voice = self.elevenlabs.Voice(voice_id=self.voice_id)
            if self.stability is not None and self.similarity_boost is not None:
                voice.settings = self.elevenlabs.VoiceSettings(
                    stability=self.stability, similarity_boost=self.similarity_boost
                )
            url = self.make_url()

            headers = {"xi-api-key": self.api_key}
            body = {
                "text": message.text,
                "voice_settings": voice.settings.dict() if voice.settings else None,
            }
            if self.model_id:
                body["model_id"] = self.model_id

            create_speech_span = tracer.start_span(
                f"synthesizer.{SynthesizerType.ELEVEN_LABS.value.split('_', 1)[-1]}.create_first",
            )
            session = self.aiohttp_session
            response = await self.make_request(session, url, body, headers)
            if self.experimental_streaming:
                result = SynthesisResult(
                    self.experimental_mp3_streaming_output_generator(
                        response, chunk_size, create_speech_span, message
                    ),  # should be wav
                    lambda seconds: self.get_message_cutoff_from_voice_speed(
                        message, seconds, self.words_per_minute
                    ),
                )
                if return_tuple:
                    return result, message
                else:
                    return result
            else:
                audio_data = await response.read()
                create_speech_span.end()
                convert_span = tracer.start_span(
                    f"synthesizer.{SynthesizerType.ELEVEN_LABS.value.split('_', 1)[-1]}.convert",
                )

                result = self.get_result_from_mp3_audio_data(
                    audio_data, message, chunk_size
                )

                convert_span.end()
                if return_tuple:
                    return result, message
                else:
                    return result

        return_with_elevenlabs_task = asyncio.create_task(
            return_with_elevenlabs(), name="return_with_elevenlabs"
        )

        # Wait for either of the tasks to complete
        done, pending = await asyncio.wait(
            [return_with_index_task, return_with_elevenlabs_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        faster_task = done.pop()
        pending_task = pending.pop()
        result = faster_task.result()  # pop the task that completed first
        self.logger.debug(f"Faster task: {faster_task.get_name() }")
        if result is not None:
            pending_task.cancel()
            return result
        else:
            self.logger.debug(
                f"Faster task returned None, awaiting pending task: {pending_task.get_name()}"
            )
            result = await pending_task
            return result

    async def make_request(self, session, url, body, headers):
        max_retries = 3
        retry_delay = 1  # seconds

        for retry_count in range(max_retries + 1):
            try:
                response = await session.request(
                    "POST",
                    url,
                    json=body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                )
                if not response.ok:
                    self.logger.debug(
                        f"ElevenLabs API returned {response.status} status code"
                    )
                response.raise_for_status()  # Raise an HTTPError for bad responses

                # If the response is okay, return it
                return response

            except aiohttp.ClientError as e:
                print(f"Attempt {retry_count + 1} failed: {e}")

                # Sleep before the next retry
                await asyncio.sleep(retry_delay)

        # If all retries fail, raise an exception
        raise Exception(f"Failed after {max_retries} retries")

    def make_url(self):
        url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{self.voice_id}"

        if self.experimental_streaming:
            url += "/stream"

        if self.optimize_streaming_latency:
            url += f"?optimize_streaming_latency={self.optimize_streaming_latency}"
        return url
