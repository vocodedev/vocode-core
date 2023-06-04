import asyncio
from typing import Optional
import wave

from fastapi import WebSocket
from vocode.streaming.models.audio_encoding import AudioEncoding
from vocode.streaming.output_device.base_output_device import BaseOutputDevice


class VonageOutputDevice(BaseOutputDevice):
    def __init__(self, ws: Optional[WebSocket] = None):
        super().__init__(sampling_rate=16000, audio_encoding=AudioEncoding.LINEAR16)
        self.ws = ws
        self.active = True
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.process_task = asyncio.create_task(self.process())
        self.tmp_file = wave.open("vonage.wav", "wb")
        self.tmp_file.setnchannels(1)
        self.tmp_file.setsampwidth(2)
        self.tmp_file.setframerate(self.sampling_rate)

    async def process(self):
        while self.active:
            chunk = await self.queue.get()
            self.tmp_file.writeframes(chunk)
            await self.ws.send_bytes(chunk)

    def consume_nonblocking(self, chunk: bytes):
        self.queue.put_nowait(chunk)

    def maybe_send_mark_nonblocking(self, message_sent):
        pass

    def terminate(self):
        self.process_task.cancel()
