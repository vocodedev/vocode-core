import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

from typing import Any, List, Optional, Tuple
from xml.etree import ElementTree
import aiohttp
from vocode import getenv
from opentelemetry.context.context import Context

from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage, SSMLMessage

from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    FILLER_PHRASES,
    FILLER_AUDIO_PATH,
    FillerAudio,
    encode_as_wav,
    tracer,
)
from vocode.streaming.models.synthesizer import NoPauseSynthesizerConfig, SynthesizerType
from vocode.streaming.models.audio_encoding import AudioEncoding


class NoPauseSynthesizer(BaseSynthesizer[NoPauseSynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: NoPauseSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(synthesizer_config, aiohttp_session)

        import nopause

        self.sdk = nopause
        self.logger = logger or logging.getLogger(__name__)
        self.thread_pool_executor = ThreadPoolExecutor(max_workers=1)

        self.dual_stream = True
        self.text_queue = None
        self.audio_chunks = None

    async def create_text_generator(self):
        first_receive = False
        while True:
            try:
                text = await self.text_queue.get()
                if not first_receive:
                    self.logger.debug('Got first stream text')
                    first_receive = True
                if text is None:
                    self.logger.debug('Got end stream text')
                    break
                self.logger.debug(f'Stream text: {text}')
                yield text
            except asyncio.CancelledError:
                self.logger.warn('Canceled: create_text_generator')
                break
            except Exception as e:
                raise e
        self.text_queue = None

    async def create_response_generator(self, audio_chunks):
        try:
            async for chunk in audio_chunks:
                self.logger.debug(f'Stream audio chunk: {chunk.chunk_id}')
                yield SynthesisResult.ChunkResult(chunk.data, False)
            yield SynthesisResult.ChunkResult(b'\x00'*2, True)
        except asyncio.CancelledError:
            self.logger.warn('Canceled: create_response_generator')
            await self.interrupt()
        self.audio_chunks = None
            
    async def create_speech_stream(self, text: str, is_end: bool = False):
        synthesis_result = None
        if self.text_queue is None:
            self.text_queue = asyncio.Queue()
            audio_chunks = await self.sdk.Synthesis.astream(
                self.create_text_generator(),
                voice_id=self.synthesizer_config.voice_id,
                model_name=self.synthesizer_config.model_name,
                language=self.synthesizer_config.language,
                api_key=self.synthesizer_config.api_key,
                api_base=self.synthesizer_config.api_base,
                api_version=self.synthesizer_config.api_version,
            )
            self.audio_chunks = audio_chunks
            synthesis_result = SynthesisResult(
                chunk_generator=self.create_response_generator(audio_chunks),
                get_message_up_to=lambda seconds: text
            )
        if text != "":
            await self.text_queue.put(text)
        if is_end:
            await self.text_queue.put(None)
        return synthesis_result
    
    async def tear_down(self):
        await super().tear_down()
        await self.interrupt()

    async def interrupt(self):
        if self.audio_chunks is not None:
            await self.audio_chunks.aterminate()

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        assert NotImplementedError
