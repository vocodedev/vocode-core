import asyncio
import json
import logging
import websockets
from websockets.client import WebSocketClientProtocol
import audioop
from urllib.parse import urlencode
from vocode import getenv
import time

from vocode.streaming.transcriber.base_transcriber import (
    BaseTranscriber,
    Transcription,
)
from vocode.streaming.models.transcriber import (
    RevAITranscriberConfig,
    EndpointingConfig,
    EndpointingType,
)
from vocode.streaming.models.audio_encoding import AudioEncoding


NUM_RESTARTS = 5

def getSeconds():
    return time.time()

class RevAITranscriber(BaseTranscriber):
    def __init__(
        self,
        transcriber_config: RevAITranscriberConfig,
        logger: logging.Logger = None,
        api_key: str = None,
    ):
        super().__init__(transcriber_config)
        self.api_key = api_key or getenv("REV_AI_API_KEY")
        if not self.api_key:
            raise Exception(
                "Please set REV_AI_API_KEY environment variable or pass it as a parameter"
            )
        self.transcriber_config = transcriber_config
        self.closed = False
        self.is_ready = True
        self.logger = logger or logging.getLogger(__name__)

    async def ready(self):
        return self.is_ready


    def get_rev_ai_url(self):
        codec = 'audio/x-raw'
        layout = 'interleaved'
        rate = self.transcriber_config.sampling_rate
        audio_format = 'S16LE'
        channels = 1

        content_type = f"{codec};layout={layout};rate={rate};format={audio_format};channels={channels}"

        url_params_dict = {
            "access_token": self.api_key,
            "content_type": content_type,
        }

        url_params_arr = [f'{key}={value}' for (key, value) in url_params_dict.items()]
        url = f"wss://api.rev.ai/speechtotext/v1/stream?" + '&'.join(url_params_arr)
        return url


    async def run(self):
        restarts = 0
        while not self.closed and restarts < NUM_RESTARTS:
            await self.process()
            restarts += 1
            self.logger.debug(
                "Rev AI connection died, restarting, num_restarts: %s", restarts
            )

    async def process(self):
        self.audio_queue = asyncio.Queue()

        async with websockets.connect(self.get_rev_ai_url()) as ws:
            async def sender(ws: WebSocketClientProtocol):
                while not self.closed:
                    try:
                        data = await asyncio.wait_for(self.audio_queue.get(), 5)
                    except asyncio.exceptions.TimeoutError:
                        break
                    await ws.send(data)
                ws.close()
                self.logger.debug("Terminating Rev.AI transcriber sender")

            async def receiver(ws: WebSocketClientProtocol):
                buffer = ""

                while not self.closed:
                    try:
                        msg = await ws.recv()
                    except Exception as e:
                        self.logger.debug(f"Got error {e} in Rev.AI receiver")
                        break
                    data = json.loads(msg)

                    if (data['type'] == 'connected'):
                        continue                    

                    is_done = data['type'] == 'final'
                    if ((len(buffer) > 0)
                        and (self.transcriber_config.endpointing_config)
                        and (self.transcriber_config.endpointing_config.type == EndpointingType.TIME_BASED)
                        and (getSeconds() > self.last_signal_seconds + self.transcriber_config.endpointing_config.time_cutoff_seconds)):
                        is_done = True

                    new_text = ''.join([e['value'] for e in data['elements']])
                    if len(new_text) > len(buffer):
                        self.last_signal_seconds = getSeconds()
                    buffer = new_text

                    confidence = 1.0
                    if is_done:
                        await self.on_response(Transcription(buffer, confidence, True))
                        buffer = ""
                    else:
                        await self.on_response(
                            Transcription(
                                buffer,
                                confidence,
                                False,
                            )
                        )

                self.logger.debug("Terminating Rev.AI transcriber receiver")

            await asyncio.gather(sender(ws), receiver(ws))

    def send_audio(self, chunk):
        self.audio_queue.put_nowait(chunk)

    def terminate(self):
        terminate_msg = json.dumps({"type": "CloseStream"})
        self.audio_queue.put_nowait(terminate_msg)
        self.closed = True
