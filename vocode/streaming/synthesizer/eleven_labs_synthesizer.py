import asyncio
import logging
import time
import os
import io
from typing import List, Any, AsyncGenerator, Optional, Tuple, Union, Dict
import wave
import aiohttp
from opentelemetry.trace import Span
from pydub import AudioSegment
from langchain.docstore.document import Document
import base64
from botocore.client import Config
from vocode import getenv
from vocode.streaming.synthesizer.base_synthesizer import (
    # BaseSynthesizer, # this wont reflect the changes in the base_synthesizer.py when editing
    SynthesisResult,
    FILLER_PHRASES,
    FILLER_KEY,
    FOLLOW_UP_PHRASES,
    FillerAudio,
    encode_as_wav,
    tracer,
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

ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVEN_LABS_BASE_URL = "https://api.elevenlabs.io/v1/"

SIMILARITY_THRESHOLD = 0.98

s3_config = Config(s3={'use_accelerate_endpoint': True})
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
        self.vector_db = None
        self.vector_db_cache = synthesizer_config.index_cache
        self.bucket_name = None

        if synthesizer_config.index_config:
            from vocode.streaming.vector_db.pinecone import PineconeDB
            self.vector_db = PineconeDB(synthesizer_config.index_config.pinecone_config)
            self.bucket_name = synthesizer_config.index_config.bucket_name
        if self.vector_db_cache:
            self.logger.debug(f"Vector DB CACHE size: {len(self.vector_db_cache)}")

    async def download_filler_audio_data(self, filler_phrase: BaseMessage) -> bytes:
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
            audio_is_interruptible: bool = True) -> List[FillerAudio]:
        if not os.path.exists(base_path):
            os.makedirs(base_path)
        audios = []
        for phrase in phrases:
            audio_path = await self.get_audio_data_from_cache_or_download(phrase, base_path)
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

    
    async def get_phrase_filler_audios(self) -> Dict[str,List[FillerAudio]]:
        filler_phrase_audios = {}
        audios = await self.get_audios_from_messages(FILLER_PHRASES, self.base_filler_audio_path)
        for key, phrase_text_list in FILLER_KEY.items():
            filler_phrase_audios[key] = []
            for phrase_text in phrase_text_list:
                for audio in audios:
                    if audio.message.text == phrase_text:
                        filler_phrase_audios[key].append(audio)
            
        return filler_phrase_audios
    
    async def get_phrase_follow_up_audios(
            self,
            follow_up_phrases: List[BaseMessage] = FOLLOW_UP_PHRASES
        ) -> List[FillerAudio]:
        self.logger.debug("generating follow up audios")
        follow_up_audios = await self.get_audios_from_messages(
            follow_up_phrases, 
            self.base_follow_up_audio_path
        )
        return follow_up_audios


    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
        return_tuple: Optional[bool] = False
    ) -> Union[SynthesisResult, Tuple[SynthesisResult, BaseMessage]]:
        
        if self.vector_db and self.bucket_name:
            self.logger.debug(f"Checking vector_db for \"{message.text}\"...")
            # if we are using vector_db, check if we have a similar phrase
            if self.vector_db_cache:
                if message.text in self.vector_db_cache:
                    self.logger.debug(f"Retrieving text from vector_db_cache: {message.text}")
                    audio_encoded : bytes = self.vector_db_cache[message.text]
                    # Decode the base64-encoded audio data back to bytes
                    audio_data = base64.b64decode(audio_encoded)
                    output_bytes_io = decode_mp3(audio_data)
                    result = self.create_synthesis_result_from_wav(
                        synthesizer_config=self.synthesizer_config,
                        file=output_bytes_io,
                        message=BaseMessage(text=message.text),
                        chunk_size=chunk_size,
                    )
                    if return_tuple:
                        return result, BaseMessage(text=message.text)
                    else:
                        return result

            index_filter = None
            if self.stability is not None and self.similarity_boost is not None:
                index_filter = {
                    "stability": self.stability,
                    "similarity_boost": self.similarity_boost,
                    "voice_id": self.voice_id
                }
            result_embeds: List[Tuple[Document, float]] = await self.vector_db.similarity_search_with_score(
                query=message.text,
                filter=index_filter
                )
            if result_embeds:
                doc, score = result_embeds[0] # top result
                if score > SIMILARITY_THRESHOLD:
                    self.logger.debug(f"Found similar synthesized text in vector_db: {doc.metadata}")
                    object_id = doc.metadata.get("object_key")
                    text_message = doc.page_content
                    self.logger.debug(f"Found similar synthesized text in vector_db: {text_message}")
                    self.logger.debug(f"Original text: {message.text}")
                    try:
                        async with self.aiobotocore_session.create_client('s3', config=s3_config) as _s3:
                            audio_data = await load_from_s3_async(
                                bucket_name=self.bucket_name, 
                                object_key=object_id,
                                s3_client=_s3
                            )
                            self.logger.debug(f"Adding {text_message} to cache.")
                            self.vector_db_cache[text_message] = base64.b64encode(audio_data)
                    except Exception as e:
                        self.logger.debug(f"Error loading object from S3: {str(e)}")
                        audio_data = None
                    
                    # assert audio_data is not None
                    # assert type(audio_data) == bytes

                    output_bytes_io = decode_mp3(audio_data)
                    
                    # If successful, return result. Otherwise, synthesize below.

                    result = self.create_synthesis_result_from_wav(
                        synthesizer_config=self.synthesizer_config,
                        file=output_bytes_io,
                        message=BaseMessage(text=text_message),
                        chunk_size=chunk_size,
                    )
                    
                    # TODO: cache result in self.vector_db_cache
                    if return_tuple:
                        return result, BaseMessage(text=text_message)
                    else:
                        return result

        # else synthesize

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
            result = SynthesisResult(
                self.experimental_mp3_streaming_output_generator(
                    response, chunk_size, create_speech_span
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
            output_bytes_io = decode_mp3(audio_data)

            result = self.create_synthesis_result_from_wav(
                synthesizer_config=self.synthesizer_config,
                file=output_bytes_io,
                message=message,
                chunk_size=chunk_size,
            )
            convert_span.end()
            if return_tuple:
                return result, message
            else: 
                return result

    def make_url(self):
        url = ELEVEN_LABS_BASE_URL + f"text-to-speech/{self.voice_id}"

        if self.experimental_streaming:
            url += "/stream"

        if self.optimize_streaming_latency:
            url += f"?optimize_streaming_latency={self.optimize_streaming_latency}"
        return url
