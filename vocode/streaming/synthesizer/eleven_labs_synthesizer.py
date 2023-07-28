import asyncio
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
from vocode.streaming.utils.worker import PydubWorker


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

        # Create a PydubWorker instance as an attribute
        self.pydub_worker = PydubWorker(
            synthesizer_config, asyncio.Queue(), asyncio.Queue()
        )
        # Start the PydubWorker and store the task
        self.pydub_worker_task = self.pydub_worker.start()

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
            raise Exception(f"ElevenLabs API returned {response.status} status code")

        async def output_generator(
            response, session
        ) -> AsyncGenerator[SynthesisResult.ChunkResult, None]:
            stream_reader = response.content
            buffer = bytearray()

            # Create a task to send the mp3 chunks to the PydubWorker's input queue in a separate loop
            async def send_chunks():
                async for chunk in stream_reader.iter_any():
                    at_eof = stream_reader.at_eof()
                    # Send the mp3 chunk and the flag to the PydubWorker's input queue
                    self.pydub_worker.consume_nonblocking((chunk, at_eof))
                    # If this is the last chunk, break the loop
                    if at_eof:
                        break

            send_task = asyncio.create_task(send_chunks())

            # Await the output queue of the PydubWorker and yield the wav chunks in another loop
            while True:
                # Get the wav chunk and the flag from the output queue of the PydubWorker
                wav_chunk, is_last = await self.pydub_worker.output_queue.get()

                buffer.extend(wav_chunk)

                if len(buffer) >= chunk_size or is_last:
                    if is_last:
                        await session.close()
                    yield SynthesisResult.ChunkResult(buffer, is_last)
                    buffer.clear()
                # If this is the last chunk, break the loop
                if is_last:
                    create_speech_span.end()
                    break

            # Wait for the send task to finish and close the session
            await asyncio.gather(
                send_task,
                session.close(),
            )

        

        return SynthesisResult(
            output_generator(response, session),  # should be wav
            lambda _: "",  # useless for now
        )
