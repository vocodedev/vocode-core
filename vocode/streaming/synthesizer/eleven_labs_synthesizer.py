import asyncio
import base64
import json
import logging
from typing import AsyncGenerator, Optional

import aiohttp
import websockets

from vocode import getenv
from vocode.streaming.agent.bot_sentiment_analyser import BotSentiment
from vocode.streaming.constants import TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import (
    ElevenLabsSynthesizerConfig,
    SynthesizerType, )
from vocode.streaming.synthesizer.base_synthesizer import (
    BaseSynthesizer,
    SynthesisResult,
    tracer,
)
from vocode.streaming.utils import get_chunk_size_per_second
from vocode.streaming.utils.mp3_helper import decode_mp3

ELEVENLABS_BASE_URL = "api.elevenlabs.io/v1"

ADAM_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
ELEVENLABS_BASE_HTTP_URL = f"https://{ELEVENLABS_BASE_URL}/"


async def text_chunker(chunks: AsyncGenerator[str, None]):
    """Split text into chunks, ensuring to not break sentences.
    This may not work non english scripts like Hindi.
    Copied from https://docs.elevenlabs.io/api-reference/text-to-speech-websockets#example-of-voice-streaming-using-elevenlabs-and-chatgpt"""
    splitters = (".", ",", "?", "!", ";", ":", "—", "-", "(", ")", "[", "]", "}", " ")
    buffer = ""

    async for text in chunks:
        if buffer.endswith(splitters):
            yield buffer + " "
            buffer = text
        elif text.startswith(splitters):
            yield buffer + text[0] + " "
            buffer = text[1:]
        else:
            buffer += text

    if buffer:
        yield buffer + " "


class ElevenLabsSynthesizer(BaseSynthesizer[ElevenLabsSynthesizerConfig]):
    def __init__(
            self,
            synthesizer_config: ElevenLabsSynthesizerConfig,
            logger: Optional[logging.Logger] = None,
            aiohttp_session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(synthesizer_config, aiohttp_session)

        import elevenlabs

        self.logger = logger or logging.getLogger(__name__)
        self.elevenlabs = elevenlabs
        self.text_queue = None
        self.text_generator = None
        self.dual_stream = True
        self.audio_chunks: AsyncGenerator[bytes, None] = None

        self.api_key = synthesizer_config.api_key or getenv("ELEVEN_LABS_API_KEY")
        self.voice_id = synthesizer_config.voice_id or ADAM_VOICE_ID
        self.stability = synthesizer_config.stability
        self.similarity_boost = synthesizer_config.similarity_boost
        self.model_id = synthesizer_config.model_id
        self.optimize_streaming_latency = synthesizer_config.optimize_streaming_latency
        self.words_per_minute = 150
        self.experimental_streaming = synthesizer_config.experimental_streaming
        self.uri = f"wss://{ELEVENLABS_BASE_URL}/text-to-speech/{self.voice_id}/stream-input?model_id={self.model_id}"

    async def create_text_generator(self):
        # yield "Hi. How are you doing."
        # yield "What can I do for you"
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
        self.text_queue = None
        self.text_generator = None

    async def generate_speech_output_chunks(self):
        async with websockets.connect(self.uri) as ws:
            await ws.send(json.dumps({
                "text": " ",
                "voice_settings": {"stability": self.stability, "similarity_boost": self.similarity_boost},
                "xi_api_key": self.api_key,
            }))
            async for text in text_chunker(self.text_generator):
                self.logger.debug(f"sending text over socket: {text}")
                await ws.send(json.dumps({"text": text, "try_trigger_generation": True}))
            await ws.send(json.dumps({"text": ""}))
            """Listen to the websocket for audio data and stream it."""
            while True:
                try:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if data.get("audio"):
                        yield base64.b64decode(data["audio"])
                    elif data.get('isFinal'):
                        break
                except websockets.ConnectionClosed:
                    print("Connection closed")
                    break
            self.logger.debug(f"socket may get closed now")

    async def create_speech_stream(self, text: str, is_end: bool = False):
        create_speech_span = tracer.start_span(
            f"synthesizer.{SynthesizerType.ELEVEN_LABS.value.split('_', 1)[-1]}.create_total",
        )
        synthesis_result = None
        if self.text_queue is None:
            self.text_queue = asyncio.Queue()
            self.text_generator = self.create_text_generator()
            audio_chunks = self.generate_speech_output_chunks()
            self.audio_chunks = audio_chunks
            message = BaseMessage(text=text, is_end=is_end)
            chunk_size = get_chunk_size_per_second(
                self.get_synthesizer_config().audio_encoding,
                self.get_synthesizer_config().sampling_rate,
            ) * TEXT_TO_SPEECH_CHUNK_SIZE_SECONDS
            synthesis_result = SynthesisResult(
                chunk_generator=self.mp3_streaming_output_generator(audio_chunks, chunk_size, create_speech_span),
                get_message_up_to=lambda seconds: self.get_message_cutoff_from_voice_speed(
                    message, seconds, self.words_per_minute
                ),
            )
        if text != "":
            await self.text_queue.put(text)
        if is_end:
            await self.text_queue.put(None)
        return synthesis_result

    async def ready(self):
        self.logger.debug(f"Readying...")

    async def tear_down(self):
        await super().tear_down()
        await self.cancel()

    async def cancel(self):
        self.logger.debug(f"Cancelling...")
        if self.text_queue is not None:
            await self.text_queue.put(None)
        if self.audio_chunks is not None:
            await self.audio_chunks.aclose()
        if self.text_generator is not None:
            # make sure the text_generator exited
            async for x in self.text_generator:
                pass

    async def interrupt(self):
        self.logger.debug(f"Interrupting...")
        await self.cancel()
        await self.ready()

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
        url = ELEVENLABS_BASE_HTTP_URL + f"text-to-speech/{self.voice_id}"

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
                synthesizer_config=self.synthesizer_config,
                file=output_bytes_io,
                message=message,
                chunk_size=chunk_size,
            )
            convert_span.end()

            return result