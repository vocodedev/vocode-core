import asyncio
import audioop
import json
from typing import Optional
from urllib.parse import urlencode

import websockets
from loguru import logger

from vocode import getenv
from vocode.streaming.models.audio import AudioEncoding
from vocode.streaming.models.transcriber import SmallestAITranscriberConfig, Transcription
from vocode.streaming.transcriber.base_transcriber import BaseAsyncTranscriber

SMALLEST_AI_STT_WS_URL = "wss://api.smallest.ai/waves/v1/pulse/get_text"
# Smallest AI STT requires 16kHz LINEAR16 audio
REQUIRED_SAMPLE_RATE = 16000
NUM_RESTARTS = 5


class SmallestAITranscriber(BaseAsyncTranscriber[SmallestAITranscriberConfig]):
    def __init__(self, transcriber_config: SmallestAITranscriberConfig):
        super().__init__(transcriber_config)
        self.api_key = transcriber_config.api_key or getenv("SMALLEST_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Missing Smallest AI API key. Set SMALLEST_API_KEY env var or pass api_key."
            )
        self._ended = False
        self.is_ready = False

        if transcriber_config.audio_encoding == AudioEncoding.MULAW:
            self._needs_ulaw_conversion = True
        else:
            self._needs_ulaw_conversion = False

    def _get_ws_url(self) -> str:
        params: dict = {
            "sample_rate": REQUIRED_SAMPLE_RATE,
            "encoding": "linear16",
        }
        if self.transcriber_config.language:
            params["language"] = self.transcriber_config.language
        return f"{SMALLEST_AI_STT_WS_URL}?{urlencode(params)}"

    async def _run_loop(self):
        restarts = 0
        while not self._ended and restarts < NUM_RESTARTS:
            await self._process()
            restarts += 1
            if not self._ended:
                logger.debug(
                    f"Smallest AI STT connection lost, restarting ({restarts}/{NUM_RESTARTS})"
                )

    async def terminate(self):
        self._ended = True
        await super().terminate()

    async def _process(self):
        url = self._get_ws_url()
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            async with websockets.connect(url, extra_headers=headers) as ws:
                self.is_ready = True
                logger.debug("Smallest AI STT WebSocket connected")

                async def sender():
                    while not self._ended:
                        try:
                            chunk = await asyncio.wait_for(self._input_queue.get(), timeout=5)
                        except asyncio.TimeoutError:
                            continue

                        if self._needs_ulaw_conversion:
                            chunk = audioop.ulaw2lin(chunk, 2)

                        # Downsample if needed (source may be higher than 16kHz)
                        if (
                            self.transcriber_config.sampling_rate != REQUIRED_SAMPLE_RATE
                            and not self._needs_ulaw_conversion
                        ):
                            chunk, _ = audioop.ratecv(
                                chunk,
                                2,
                                1,
                                self.transcriber_config.sampling_rate,
                                REQUIRED_SAMPLE_RATE,
                                None,
                            )

                        try:
                            await ws.send(chunk)
                        except websockets.exceptions.ConnectionClosed:
                            break
                    logger.debug("Smallest AI STT sender done")

                async def receiver():
                    while not self._ended:
                        try:
                            raw = await ws.recv()
                        except websockets.exceptions.ConnectionClosed as e:
                            logger.debug(f"Smallest AI STT connection closed: {e}")
                            break
                        except Exception as e:
                            logger.error(f"Smallest AI STT receiver error: {e}")
                            break

                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        transcript = data.get("transcript") or data.get("full_transcript", "")
                        is_final = data.get("is_final", False)
                        confidence = data.get("confidence", 1.0)

                        if transcript:
                            self.produce_nonblocking(
                                Transcription(
                                    message=transcript,
                                    confidence=confidence,
                                    is_final=is_final,
                                )
                            )

                await asyncio.gather(sender(), receiver())

        except websockets.exceptions.WebSocketException as e:
            logger.error(f"Smallest AI STT WebSocket error: {e}")
        except Exception as e:
            logger.error(f"Smallest AI STT unexpected error: {e}")
        finally:
            self.is_ready = False
