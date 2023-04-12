import asyncio
import json
import logging
import websockets
from urllib.parse import urlencode
from vocode import getenv

from vocode.streaming.models.transcriber import AssemblyAITranscriberConfig
from vocode.streaming.models.websocket import AudioMessage
from vocode.streaming.transcriber.base_transcriber import (
    BaseTranscriber,
    Transcription,
)
from vocode.streaming.models.audio_encoding import AudioEncoding


ASSEMBLY_AI_URL = "wss://api.assemblyai.com/v2/realtime/ws"


class AssemblyAITranscriber(BaseTranscriber):
    def __init__(
        self,
        transcriber_config: AssemblyAITranscriberConfig,
        logger: logging.Logger = None,
        api_key: str = None,
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
        self.audio_queue = asyncio.Queue()

    async def ready(self):
        return True

    async def run(self):
        await self.process()

    def send_audio(self, chunk):
        self.audio_queue.put_nowait(chunk)

    def terminate(self):
        terminate_msg = json.dumps({"terminate_session": True})
        self.audio_queue.put_nowait(terminate_msg)
        self._ended = True

    def get_assembly_ai_url(self):
        return ASSEMBLY_AI_URL + f"?sample_rate={self.transcriber_config.sampling_rate}"

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
                        data = await asyncio.wait_for(self.audio_queue.get(), 5)
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
                    except websockets.exceptions.ConnectionClosedError as e:
                        self.logger.debug(e)
                        break
                    except Exception as e:
                        assert False, "Not a websocket 4008 error"

                    data = json.loads(result_str)
                    is_final = (
                        "message_type" in data
                        and data["message_type"] == "FinalTranscript"
                    )
                    if "text" in data and data["text"]:
                        await self.on_response(
                            Transcription(data["text"], data["confidence"], is_final)
                        )

            await asyncio.gather(sender(ws), receiver(ws))
