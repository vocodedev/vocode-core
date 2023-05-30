import asyncio
import json
import logging
from typing import Optional
import websockets
import audioop
import numpy as np
from urllib.parse import urlencode
from vocode import getenv

from vocode.streaming.models.transcriber import AssemblyAITranscriberConfig
from vocode.streaming.models.websocket import AudioMessage
from vocode.streaming.transcriber.base_transcriber import (
    BaseAsyncTranscriber,
    Transcription,
)
from vocode.streaming.models.audio_encoding import AudioEncoding


ASSEMBLY_AI_URL = "wss://api.assemblyai.com/v2/realtime/ws"


class AssemblyAITranscriber(BaseAsyncTranscriber[AssemblyAITranscriberConfig]):
    def __init__(
        self,
        transcriber_config: AssemblyAITranscriberConfig,
        api_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(transcriber_config)
        self.api_key = api_key or getenv("ASSEMBLY_AI_API_KEY")
        if not self.api_key:
            raise Exception(
                "Please set ASSEMBLY_AI_API_KEY environment variable or pass it as a parameter"
            )
        self._ended = False
        self.logger = logger or logging.getLogger(__name__)
        if self.transcriber_config.endpointing_config:
            raise Exception("Assembly AI endpointing config not supported yet")

        self.buffer = bytearray()

    async def ready(self):
        return True

    async def _run_loop(self):
        await self.process()

    def send_audio(self, chunk):
        if self.transcriber_config.audio_encoding == AudioEncoding.MULAW:
            sample_width = 1
            if isinstance(chunk, np.ndarray):
                chunk = chunk.astype(np.int16)
                chunk = chunk.tobytes()
            chunk = audioop.ulaw2lin(chunk, sample_width)

        self.buffer.extend(chunk)

        if (
            len(self.buffer) / (2 * self.transcriber_config.sampling_rate)
        ) >= self.transcriber_config.buffer_size_seconds:
            self.input_queue.put_nowait(self.buffer)
            self.buffer = bytearray()

    def terminate(self):
        terminate_msg = json.dumps({"terminate_session": True})
        self.input_queue.put_nowait(terminate_msg)
        self._ended = True

    def get_assembly_ai_url(self):
        url_params = {"sample_rate": self.transcriber_config.sampling_rate}
        if self.transcriber_config.word_boost:
            url_params.update(
                {"word_boost": json.dumps(self.transcriber_config.word_boost)}
            )
        return ASSEMBLY_AI_URL + f"?{urlencode(url_params)}"

    async def process(self):
        URL = self.get_assembly_ai_url()

        async with websockets.connect(
            URL,
            extra_headers=(("Authorization", self.api_key),),
            ping_interval=5,
            ping_timeout=20,
        ) as ws:
            await asyncio.sleep(0.1)

            async def sender(ws):  # sends audio to websocket
                while not self._ended:
                    try:
                        data = await asyncio.wait_for(self.input_queue.get(), 5)
                    except asyncio.exceptions.TimeoutError:
                        break
                    await ws.send(
                        json.dumps({"audio_data": AudioMessage.from_bytes(data).data})
                    )
                self.logger.debug("Terminating AssemblyAI transcriber sender")

            async def receiver(ws):
                while not self._ended:
                    try:
                        result_str = await ws.recv()
                        data = json.loads(result_str)
                        if "error" in data and data["error"]:
                            raise Exception(data["error"])
                    except websockets.exceptions.ConnectionClosedError as e:
                        self.logger.debug(e)
                        break

                    data = json.loads(result_str)
                    is_final = (
                        "message_type" in data
                        and data["message_type"] == "FinalTranscript"
                    )
                    if "text" in data and data["text"]:
                        self.output_queue.put_nowait(
                            Transcription(
                                message=data["text"],
                                confidence=data["confidence"],
                                is_final=is_final,
                            )
                        )

            await asyncio.gather(sender(ws), receiver(ws))
