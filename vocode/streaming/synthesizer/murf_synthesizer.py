import asyncio
import base64
import copy
import hashlib
import json
import uuid
from typing import List, Optional, Tuple

import websockets
from loguru import logger
from websockets.asyncio.client import ClientConnection

from vocode import getenv
from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.synthesizer import MurfSynthesizerConfig
from vocode.streaming.synthesizer.base_synthesizer import BaseSynthesizer, SynthesisResult


class MurfSynthesizer(BaseSynthesizer[MurfSynthesizerConfig]):
    def __init__(self, synthesizer_config: MurfSynthesizerConfig):
        super().__init__(synthesizer_config)

        self.api_key = synthesizer_config.api_key or getenv("MURF_API_KEY")
        if not self.api_key:
            raise ValueError("Missing Murf API key")

        self.voice_id = synthesizer_config.voice_id
        self.sampling_rate = synthesizer_config.sampling_rate or 16000
        self.audio_encoding = synthesizer_config.audio_encoding or AudioEncoding.LINEAR16
        self.audio_format = synthesizer_config.format or "PCM"
        self.channel_type = synthesizer_config.channel_type or "MONO"
        self.style = synthesizer_config.style or "Conversational"
        self.rate = synthesizer_config.rate or 0
        self.pitch = synthesizer_config.pitch or 0
        self.variation = synthesizer_config.variation or 1
        self.multi_native_locale = synthesizer_config.multi_native_locale or None

        self.num_channels = 1
        self.ws: Optional[ClientConnection] = None
        self.context_id: Optional[str] = None
        self.clear_context_task: Optional[asyncio.Task] = None
        self.clear_context_lock = asyncio.Lock()

        self.ctx_message = BaseMessage(text="")
        self.ctx_timestamps: List[Tuple[str, float, float]] = []

    async def _try_ws_connect(self) -> bool:
        try:
            logger.debug(
                f"Connecting to Murf WebSocket with API key: {self.api_key} {self.sampling_rate} {self.audio_format} {self.channel_type}"
            )
            self.ws = await websockets.connect(
                f"wss://api.murf.ai/v1/speech/stream-input"
                f"?api-key={self.api_key}&sample_rate={self.sampling_rate}"
                f"&format={self.audio_format}&channel_type={self.channel_type}"
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to Murf WebSocket: {e}")
            return False

    async def initialize_ws(self, max_retries: int = 3, initial_backoff: float = 1.0):
        if self.ws is None:
            backoff = initial_backoff
            for attempt in range(max_retries):
                if await self._try_ws_connect():
                    logger.debug("WebSocket connection initialized")
                    return
                if attempt < max_retries - 1:
                    wait_time = backoff * (2**attempt)
                    logger.debug(f"Retrying connection in {wait_time:.1f} seconds...")
                    await asyncio.sleep(wait_time)
            raise ConnectionError("Failed to establish WebSocket connection after maximum retries")

    async def initialize_ctx(self, is_first_text_chunk: bool):
        if self.context_id is None or is_first_text_chunk:
            if self.context_id and is_first_text_chunk:
                await self.clear_context()
            self.context_id = str(uuid.uuid4())
            logger.debug(f"Using new context_id: {self.context_id}")

    async def clear_context(self):
        async with self.clear_context_lock:
            if self.clear_context_task:
                self.clear_context_task.cancel()
                self.clear_context_task = None
            if self.context_id and self.ws:
                try:
                    await self.ws.send(json.dumps({"clear": True, "context_id": self.context_id}))
                    logger.debug(f"Cleared context_id: {self.context_id}")
                except Exception as e:
                    logger.warning(f"Error clearing context: {e}")

    async def no_more_inputs(self):
        if not self.ws:
            logger.warning("WebSocket connection is not initialized")
            return

        try:
            await self.ws.send(
                json.dumps(
                    {
                        "text": "",
                        "end": True,
                        "context_id": self.context_id,
                    }
                )
            )
            logger.debug(f"Successfully sent no_more_inputs for context_id: {self.context_id}")
        except Exception as e:
            logger.error(f"Failed to send no_more_inputs for context_id {self.context_id}: {e}")

    def refresh_no_more_inputs_task(self):
        logger.debug(f"refresh_no_more_inputs_task context_id: {self.context_id}")
        if self.clear_context_task:
            self.clear_context_task.cancel()

        async def delayed_clear():
            await asyncio.sleep(1.0)
            await self.no_more_inputs()

        self.clear_context_task = asyncio.create_task(delayed_clear())

    async def create_speech_uncached(
        self,
        message: BaseMessage,
        chunk_size: int,
        is_first_text_chunk: bool = False,
        is_sole_text_chunk: bool = False,
    ) -> SynthesisResult:
        try:
            await self.initialize_ws()
            await self.initialize_ctx(is_first_text_chunk)

            if not self.ws:
                raise ConnectionError("WebSocket connection is not initialized")

            logger.debug(
                f"Sending message with context_id={self.context_id}, text='{message.text}' is_sole_text_chunk={is_sole_text_chunk} is_first_text_chunk={is_first_text_chunk}"
            )

            try:
                await self.ws.send(
                    json.dumps(
                        {
                            "voice_config": {
                                "voice_id": self.voice_id,
                                "style": self.style,
                                "rate": self.rate,
                                "pitch": self.pitch,
                                "variation": self.variation,
                                "multi_native_locale": self.multi_native_locale,
                                "context_id": self.context_id,
                            },
                            "text": message.text,
                            "context_id": self.context_id,
                            "end": is_sole_text_chunk,
                        }
                    )
                )
            except websockets.exceptions.WebSocketException as e:
                logger.warning(f"WebSocket error while sending message: {e}")
                self.ws = None
                raise

            if not is_sole_text_chunk:
                self.refresh_no_more_inputs_task()

            self.ctx_message.text += message.text

            async def chunk_generator():
                buffer = bytearray()
                try:
                    while True:
                        try:
                            raw = await asyncio.wait_for(self.ws.recv(), timeout=30.0)
                            response = json.loads(raw)
                            response_copy = copy.deepcopy(response)

                            if response.get("error"):
                                logger.error(f"Murf WS error: {response.get('error')}")
                                self.ws = None
                                break
                            else:
                                if response_copy.get("audio"):
                                    response_copy["audio"] = "REDACTED"
                        except websockets.exceptions.WebSocketException as e:
                            logger.warning(f"WebSocket error while receiving: {e}")
                            self.ws = None
                            break
                        except asyncio.TimeoutError:
                            logger.warning("Timeout waiting for Murf TTS WebSocket response")
                            break
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to decode WebSocket response: {e}")
                            continue

                        if response.get("final"):
                            logger.debug(f"Received is_final for context_id={self.context_id}")
                            break

                        audio_b64 = response.get("audio")
                        if not audio_b64:
                            continue

                        try:
                            audio_bytes = base64.b64decode(audio_b64)
                            buffer.extend(audio_bytes)
                        except Exception as e:
                            logger.error(f"Failed to decode audio data: {e}")
                            continue

                        while len(buffer) >= chunk_size:
                            yield SynthesisResult.ChunkResult(
                                chunk=buffer[:chunk_size],
                                is_last_chunk=False,
                            )
                            buffer = buffer[chunk_size:]

                except Exception as e:
                    logger.error(f"Error in chunk generator: {e}")
                    if isinstance(e, websockets.exceptions.WebSocketException):
                        logger.warning("WebSocket error, resetting connection state")
                        self.ws = None
                    raise

                if buffer:
                    # pad the leftover buffer with silence based on encoding
                    if len(buffer) < chunk_size:
                        padding_size = chunk_size - len(buffer)
                        if self.audio_encoding == AudioEncoding.MULAW:
                            buffer.extend(b"\x7f" * padding_size)
                        else:
                            buffer.extend(b"\x00\x00" * padding_size)
                    yield SynthesisResult.ChunkResult(chunk=buffer, is_last_chunk=True)

            def get_message_cutoff_ctx(message, seconds, words_per_minute=150):
                return self.get_message_cutoff_from_voice_speed(message, seconds, words_per_minute)

            return SynthesisResult(
                chunk_generator=chunk_generator(),
                get_message_up_to=lambda seconds: get_message_cutoff_ctx(self.ctx_message, seconds),
            )
        except websockets.exceptions.WebSocketException as e:
            logger.warning(f"WebSocket error in create_speech_uncached: {e}")
            self.ws = None
            raise
        except Exception as e:
            logger.error(f"Error in create_speech_uncached: {e}")
            raise

    @classmethod
    def get_voice_identifier(cls, synthesizer_config: MurfSynthesizerConfig):
        if not synthesizer_config.api_key:
            raise ValueError("Missing Murf API key")

        hashed_api_key = hashlib.sha256(synthesizer_config.api_key.encode("utf-8")).hexdigest()

        return ":".join(
            [
                "murf",
                hashed_api_key,
                str(synthesizer_config.voice_id),
                f"sr_{synthesizer_config.sampling_rate}",
                str(synthesizer_config.format),
                str(synthesizer_config.channel_type),
            ]
        )

    async def tear_down(self):
        try:
            async with self.clear_context_lock:
                if self.clear_context_task:
                    logger.debug("Cancelling clear context task")
                    self.clear_context_task.cancel()
                    try:
                        await self.clear_context_task
                    except asyncio.CancelledError:
                        pass
                    self.clear_context_task = None

            if self.ws:
                try:
                    logger.debug("Closing WebSocket connection")
                    await self.ws.close()
                except Exception as e:
                    logger.warning(f"Error closing WebSocket connection: {e}")
                self.ws = None

            self.context_id = None
            self.ctx_message = BaseMessage(text="")
            self.ctx_timestamps = []

            await super().tear_down()
            logger.debug("MurfSynthesizer tear down complete")
        except Exception as e:
            logger.error(f"Error during MurfSynthesizer tear down: {e}")
            raise
