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
from vocode.streaming.utils import convert_linear_audio


class NoPauseSynthesizer(BaseSynthesizer[NoPauseSynthesizerConfig]):
    def __init__(
        self,
        synthesizer_config: NoPauseSynthesizerConfig,
        logger: Optional[logging.Logger] = None,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(synthesizer_config, aiohttp_session)

        import nopause
        from nopause import AudioConfig

        self.sdk = nopause
        self.logger = logger or logging.getLogger(__name__)
        self.thread_pool_executor = ThreadPoolExecutor(max_workers=1)

        self.synthesizer = self.sdk.Synthesis(
            voice_id=self.synthesizer_config.voice_id,
            model_name=self.synthesizer_config.model_name,
            language=self.synthesizer_config.language,
            audio_config=AudioConfig(sample_rate=self.synthesizer_config.sampling_rate),
            api_key=self.synthesizer_config.api_key,
            api_base=self.synthesizer_config.api_base,
            api_version=self.synthesizer_config.api_version,
        )

        self.dual_stream = True
        self.text_queue = None
        self.text_generator = None
        self.audio_chunks = None
        self.semaphore = asyncio.Semaphore(1)
        self.interrupted = False

    async def ready(self):
        await self.synthesizer.aconnect()

    async def create_text_generator(self):
        first_receive = False
        
        try:
            while True:
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
            self.logger.warn('<> Canceled: text generator')
        except Exception as e:
            raise e
        finally:
            self.logger.warn('<> Done: text generator')
            self.text_queue = None
            self.text_generator = None

    async def create_response_generator(self, audio_chunks):
        try:
            async for chunk in audio_chunks:
                self.logger.debug(f'<> Stream audio chunk: {chunk.chunk_id}')
                data = convert_linear_audio(
                    chunk.data,
                    input_sample_rate=chunk.sample_rate,
                    output_sample_rate=self.synthesizer_config.sampling_rate,
                    output_encoding=self.synthesizer_config.audio_encoding
                    )
                yield SynthesisResult.ChunkResult(data, False)
            yield SynthesisResult.ChunkResult(b'\x00'*2, True)
            self.logger.warn('<> Done: response generator')
        except asyncio.CancelledError:
            self.logger.warn('<> Canceled: response generator')
            await self.cancel()
        except self.sdk.sdk.error.InvalidRequestError as e:
            self.logger.warn(f'<> Nopause InvalidRequestError: {str(e)}')
            await self.cancel()
        self.audio_chunks = None
            
    async def create_speech_stream(self, text: str, is_end: bool = False):
        synthesis_result = None
        if self.text_queue is None:
            in_used = await self.synthesizer.ain_use()
            if in_used:
                await self.synthesizer.ainterrupt()
            self.logger.debug(f'<> Create synthesizer stream')
            async with self.semaphore:
                self.interrupted = False
            self.text_queue = asyncio.Queue()
            self.text_generator = self.create_text_generator()
            audio_chunks = await self.synthesizer.astream(self.text_generator)
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
        await self.cancel()

    async def cancel(self):
        self.logger.warn('<> Call synthesizer.cancel')
        if self.text_queue is not None:
            self.logger.warn('<> Put none to text_queue')
            await self.text_queue.put(None)
        if self.audio_chunks is not None:
            self.logger.warn('<> Terminate audio_chunks')
            await self.audio_chunks.aterminate()
        else:
            self.logger.warn('<> Close synthesizer')
            await self.synthesizer.aclose()

    async def interrupt(self):
        async with self.semaphore:
            if not self.interrupted:
                self.logger.warn('<> Call synthesizer.interrupt')
                await self.cancel()
                self.logger.warn('<> Reconnect synthesizer')
                await self.synthesizer.aconnect()
                self.interrupted = True

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        assert NotImplementedError
