import asyncio
import base64
import json
import logging
import time
from typing import Annotated, Any, AsyncGenerator, Literal, Optional, Tuple, Union
from fastapi import WebSocket
from vocode.streaming.agent.base_agent import AgentResponse, AgentResponseMessageChunk
from vocode.streaming.models.agent import (
    EndInputStream,
    InputStreamChunk,
    InputStreamMessage,
)
from vocode.streaming.synthesizer import miniaudio_worker
import websockets
from websockets.client import WebSocketClientProtocol
import aiohttp
from opentelemetry.trace import Span
from pydantic import BaseModel, Field
from elevenlabs import generate

from vocode import getenv
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    encode_as_wav,
    tracer,
)
from vocode.streaming.models.synthesizer import (
    ElevenLabsSynthesizerConfig,
    SynthesizerType,
)
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.utils.mp3_helper import decode_mp3
from vocode.streaming.synthesizer.miniaudio_worker import MiniaudioWorker
from vocode.streaming.utils.worker import (
    AsyncQueueWorker,
    AsyncWorker,
    InterruptibleAgentResponseEvent,
)


ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVEN_LABS_BASE_URL = "https://api.elevenlabs.io/v1/"
ELEVEN_LABS_WEBSOCKET_BASE_URL = "wss://api.elevenlabs.io/v1/"


class ElevenLabsInputStreamWorker(AsyncWorker[AgentResponse]):
    def __init__(
        self,
        input_queue: asyncio.Queue[InterruptibleAgentResponseEvent[AgentResponse]],
        output_queue: asyncio.Queue[bytes | None],
        api_key: str,
        voice_id: str,
        model_id: str,
        voice_settings: Optional[dict] = None,
    ):
        super().__init__(input_queue, output_queue)
        self.api_key = api_key
        self.voice_id = voice_id
        self.model_id = model_id
        self.bos = json.dumps(
            dict(
                text=" ",
                try_trigger_generation=True,
                voice_settings=voice_settings,
                generation_config=dict(
                    chunk_length_schedule=[50],
                ),
            )
        )
        self.eos = json.dumps(dict(text=""))
        self.buffered_message = ""

    def get_message_so_far(self):
        return self.buffered_message

    async def _run_loop(self) -> None:
        url = (
            ELEVEN_LABS_WEBSOCKET_BASE_URL
            + f"text-to-speech/{self.voice_id}/stream-input?model_type={self.model_id}"
        )

        async with websockets.connect(
            url,
            extra_headers={"xi-api-key": self.api_key},
        ) as websocket:

            async def sender(websocket: WebSocketClientProtocol):
                try:
                    await websocket.send(self.bos)
                except Exception as e:
                    self.logger.error(e)
                    return
                while True:
                    item: InterruptibleAgentResponseEvent[
                        AgentResponse
                    ] = await self.input_queue.get()
                    payload = item.payload
                    input_stream_message: InputStreamMessage
                    if not isinstance(payload, AgentResponseMessageChunk):
                        break
                    else:
                        input_stream_message = payload.chunk

                    if isinstance(input_stream_message, InputStreamChunk):
                        self.buffered_message += input_stream_message.text
                        msg = dict(
                            text=input_stream_message.text, try_trigger_generation=True
                        )
                        await websocket.send(json.dumps(msg))
                    elif isinstance(input_stream_message, EndInputStream):
                        await websocket.send(self.eos)
                        break

            async def receiver(websocket: WebSocketClientProtocol):
                while True:
                    try:
                        response = await websocket.recv()
                    except websockets.exceptions.ConnectionClosed:
                        break
                    print(response)
                    try:
                        data = json.loads(response)
                        if data["audio"]:
                            self.output_queue.put_nowait(
                                base64.b64decode(data["audio"])
                            )
                    except json.JSONDecodeError:
                        continue
                    yield response

            await asyncio.gather(sender(websocket), receiver(websocket))


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

    async def create_input_streamed_speech(
        self,
        chunk_size: int,
        input_queue: asyncio.Queue[InterruptibleAgentResponseEvent[AgentResponse]],
    ):
        voice = self.get_voice()
        miniaudio_worker_input_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        input_stream_worker = ElevenLabsInputStreamWorker(
            input_queue=input_queue,
            output_queue=miniaudio_worker_input_queue,
            api_key=self.api_key,
            voice_id=self.voice_id,
            model_id=self.model_id or "eleven_monolingual_v1",
            voice_settings=voice.settings.dict() if voice.settings else None,
        )
        miniaudio_worker = MiniaudioWorker(
            synthesizer_config=self.synthesizer_config,
            chunk_size=chunk_size,
            input_queue=miniaudio_worker_input_queue,
            output_queue=asyncio.Queue(),
        )
        input_stream_worker.start()
        miniaudio_worker.start()

        async def chunk_generator():
            try:
                # Await the output queue of the MiniaudioWorker and yield the wav chunks in another loop
                while True:
                    # Get the wav chunk and the flag from the output queue of the MiniaudioWorker
                    wav_chunk, is_last = await miniaudio_worker.output_queue.get()
                    if self.synthesizer_config.should_encode_as_wav:
                        wav_chunk = encode_as_wav(wav_chunk, self.synthesizer_config)

                    yield SynthesisResult.ChunkResult(wav_chunk, is_last)
            except asyncio.CancelledError:
                pass
            finally:
                input_stream_worker.terminate()
                miniaudio_worker.terminate()

        return SynthesisResult(
            chunk_generator(),
            lambda seconds: input_stream_worker.get_message_so_far(),
        )

    def get_voice(self):
        voice = self.elevenlabs.Voice(voice_id=self.voice_id)
        if self.stability is not None and self.similarity_boost is not None:
            voice.settings = self.elevenlabs.VoiceSettings(
                stability=self.stability, similarity_boost=self.similarity_boost
            )
        return voice

    async def create_speech(
        self,
        message: BaseMessage,
        chunk_size: int,
        bot_sentiment: Optional[BotSentiment] = None,
    ) -> SynthesisResult:
        voice = self.get_voice()
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
                self.experimental_mp3_streaming_output_generator(
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
