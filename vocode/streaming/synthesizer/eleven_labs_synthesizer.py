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

from vocode import getenv
from vocode.streaming.synthesizer.base_synthesizer import (
    # BaseSynthesizer, # this wont reflect the changes in the base_synthesizer.py when editing
    SynthesisResult,
    FILLER_PHRASES,
    FILLER_AUDIO_PATH,
    FILLER_KEY,
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

from vocode.streaming.utils.aws_s3 import load_from_s3

ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVEN_LABS_BASE_URL = "https://api.elevenlabs.io/v1/"

SIMILARITY_THRESHOLD = 0.9

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
        self.vector_db_cache = {}
        self.bucket_name = None

        if synthesizer_config.index_config:
            from vocode.streaming.vector_db.pinecone import PineconeDB
            self.vector_db = PineconeDB(synthesizer_config.index_config.pinecone_config)
            self.bucket_name = synthesizer_config.index_config.bucket_name
            # TODO: cache vector_db results


    async def get_phrase_filler_audios(self) -> Dict[str,List[FillerAudio]]:
        filler_phrase_audios = {
            'question': [],
            'confirm': []
        }

        for filler_phrase in FILLER_PHRASES:
            cache_key = "-".join(
                (
                    str(filler_phrase.text),
                    str(self.synthesizer_config.type),
                    str(self.synthesizer_config.audio_encoding),
                    str(self.synthesizer_config.sampling_rate),
                    str(self.voice_id),
                    str(self.stability),
                    str(self.similarity_boost),
                )
            )
            filler_audio_path = os.path.join(FILLER_AUDIO_PATH, f"{cache_key}.wav")
            if os.path.exists(filler_audio_path):
                audio_data = open(filler_audio_path, "rb").read()
            else:
                self.logger.debug(f"Generating filler audio for {filler_phrase.text}")
                voice = self.elevenlabs.Voice(voice_id=self.voice_id)
                if self.stability is not None and self.similarity_boost is not None:
                    voice.settings = self.elevenlabs.VoiceSettings(
                        stability=self.stability, 
                        similarity_boost=self.similarity_boost
                    )
                url = self.make_url()

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
                            raise Exception(f"ElevenLabs API returned {response.status} status code")

                        audio_data = await response.read()  
                        audio_segment: AudioSegment = AudioSegment.from_mp3(
                            io.BytesIO(audio_data)  # type: ignore
                        )         

                        audio_segment.export(filler_audio_path, format="wav")

            audio_data = convert_wav(
                                filler_audio_path,
                                output_sample_rate=self.synthesizer_config.sampling_rate,
                                output_encoding=self.synthesizer_config.audio_encoding
                            )
            for key in filler_phrase_audios:
                if filler_phrase.text in FILLER_KEY[key]:
                    filler_phrase_audios[key].append(
                        FillerAudio(
                            filler_phrase,
                            audio_data = audio_data,
                            synthesizer_config=self.synthesizer_config,
                            is_interruptible=False,
                            seconds_per_chunk=2,
                        )
                    )
        return filler_phrase_audios

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
        return_tuple: Optional[bool] = False
    ) -> Union[SynthesisResult, Tuple[SynthesisResult, BaseMessage]]:
        
        if self.vector_db and self.bucket_name:
            if self.vector_db_cache:
                # TODO: search in vector_db_cache so we do not have to make api call
                # search in vector_db_cache
                # return result if found
                pass

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
                        audio_data = load_from_s3(
                            bucket_name=self.bucket_name, 
                            object_key=object_id
                        )
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
